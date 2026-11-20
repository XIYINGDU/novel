import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIDEO / "common"))

import lipsync_cache as cache
import lipsync_group as group

try:
    import segbuild as sb
except ModuleNotFoundError as exc:
    # The renderer has a separate torch/ffmpeg environment (see build_p3.py).
    if exc.name not in ("torch", "numpy", "PIL", "pydub"):
        raise
    sb = None


class MediaCache(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.inputs = self.root / "lipsync_in"
        self.inputs.mkdir()
        self.outputs = self.root / "lipsync_out"
        self.outputs.mkdir()

    def write_input(self, source):
        vid, stem = self.inputs / "vid_a.mp4", self.inputs / "stem_a.wav"
        vid.write_bytes(b"fixed-duration video")
        stem.write_bytes(b"voice")
        cache.write_stamp(vid, {"source": source, "video": cache.file_sha256(vid), "stem": cache.file_sha256(stem)})
        return vid, stem

    def test_verified_upload_and_partial_response(self):
        vid, stem = self.write_input("first")
        upload = self.root / "in.tar.gz"
        with tarfile.open(upload, "w:gz") as tf:
            for p in (vid, stem):
                tf.add(p, arcname=p.name)
        self.assertEqual(cache.upload_sources(upload, self.inputs, ["a"]), {"a": "first"})
        receipt = vid.with_suffix(".sha256")
        original = receipt.read_bytes()
        receipt.unlink()
        with self.assertRaisesRegex(ValueError, "重新 prepare"):
            cache.upload_sources(upload, self.inputs, ["a"])
        self.assertIn("a", cache.upload_sources(upload, self.inputs, ["a"], merged=True))
        receipt.write_bytes(original)
        stem.write_bytes(b"new voice")
        with self.assertRaises(ValueError):
            cache.input_key(self.inputs, "a")

        result = self.root / "sync_a.mp4"
        result.write_bytes(b"synced video")
        archive = self.root / "out.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(result, arcname=result.name)
        with self.assertRaises(KeyError):
            cache.publish_archive(archive, self.outputs, {"a": "first", "b": "second"})
        self.assertFalse((self.outputs / result.name).exists())
        cache.publish_archive(archive, self.outputs, {"a": "first"})
        output = self.outputs / result.name
        self.assertTrue(cache.matches_output(output, "first"))
        output.write_bytes(b"different")
        self.assertFalse(cache.matches_output(output, "first"))

    def test_corrupt_receipt_is_not_a_legacy_output_and_can_be_replaced(self):
        video, _ = self.write_input("A")
        video.with_suffix(".sha256").write_text("{broken")
        self.assertTrue(cache.read_stamp(video))
        with self.assertRaisesRegex(ValueError, "重新 prepare"):
            cache.input_key(self.inputs, "a")
        self.write_input("B")
        self.assertEqual(cache.input_key(self.inputs, "a"), "B")

    def test_group_split_rejects_replaced_source(self):
        self.write_input("new")
        gd = self.root / "ls_group"
        gd.mkdir()
        (gd / "group_plan.json").write_text(json.dumps({
            "groups": {"aG": {"pieces": ["a"], "counts": [1]}}, "zoom": {}, "sources": {"a": "old"}}))
        with self.assertRaisesRegex(SystemExit, "merge 后更换"):
            group.split(self.root)

    @unittest.skipUnless(sb, "requires the video build environment")
    def test_mix_isolated_and_same_length_seed_or_voice_rejected(self):
        seg = sb.Seg(self.root, "p3")
        seg.clip_dir.mkdir()
        base = seg.clip_dir / "clip_A.mp4"
        base.write_bytes(b"seed one")
        sync = seg.ls_out / "sync_a.mp4"
        sync.write_bytes(b"mouth from seed one")
        quiet = sb.AudioSegment.silent(duration=1000, frame_rate=48000)
        from pydub.generators import Sine
        voiced = Sine(660).to_audio_segment(duration=1000, volume=-24)
        def spec(fast, mix, stem):
            book = sb.ShotBook(seg, fast)
            book.add("a", 1, "clip_A", [(0, 0), (1, 16)], [], mix, ls_stem=stem, ls_dur=1)
            return book.specs[0]

        master = spec(False, quiet, voiced)
        preview = spec(True, voiced, voiced)
        source = sb.sync_source(master, cache.file_sha256(base), master["stem_sha256"])
        cache.record_output(sync, source)
        master_path, _, _ = sb.shot_inputs(seg, master, False)
        fast_path, _, _ = sb.shot_inputs(seg, preview, True)
        self.assertNotEqual(master_path.parent, fast_path.parent)
        self.assertEqual(cache.file_sha256(master_path), master["mix_sha256"])
        master_path.write_bytes(b"truncated")
        with self.assertRaisesRegex(ValueError, "混音校验"):
            sb.shot_inputs(seg, master, False)
        spec(False, quiet, voiced)
        self.assertEqual(cache.file_sha256(master_path), master["mix_sha256"])
        changed_voice = spec(False, quiet, quiet)
        with self.assertRaisesRegex(ValueError, "口型与源片或干声不符"):
            sb.shot_inputs(seg, changed_voice, False)
        base.write_bytes(b"seed two")
        with self.assertRaisesRegex(ValueError, "口型与源片或干声不符"):
            sb.shot_inputs(seg, master, False)
        self.assertIsNone(sb.shot_inputs(seg, preview, True)[1])

    @unittest.skipUnless(sb, "requires the video build environment")
    def test_legacy_render_stamp_requires_exact_material(self):
        seg = sb.Seg(self.root, "p3")
        seg.clip_dir.mkdir()
        clip = seg.clip_dir / "clip_A.mp4"
        clip.write_bytes(b"A")
        wav = seg.mix_dir / "shot_a.wav"
        wav.write_bytes(b"mix")
        sync = seg.ls_out / "sync_a.mp4"
        sync.write_bytes(b"legacy sync")
        spec = {"id": "a", "clip": "clip_A", "curve": [[0, 0]], "lipsync_dur_sec": 1}
        stamp = seg.shot_dir / "seg_master_a.sha256"
        stamp.write_text(sb.legacy_render_hash(spec, "master", cache.file_sha256(clip),
                                                cache.file_sha256(wav), cache.file_sha256(sync)))
        self.assertEqual(sb.shot_inputs(seg, spec, False)[1], sync)
        sync.write_bytes(b"different same-duration output")
        with self.assertRaisesRegex(ValueError, "旧 master 清单"):
            sb.shot_inputs(seg, spec, False)


if __name__ == "__main__":
    unittest.main()
