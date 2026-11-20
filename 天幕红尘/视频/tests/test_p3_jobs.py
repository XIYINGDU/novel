import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ep01_p3"))
import stageA_voices_p3 as voices
import stageC_scout_p3 as video


class P3JobsTest(unittest.TestCase):
    def test_hd_plan_resolves_retake_prompts_and_skips_cached_clips(self):
        plan_ids = [row["id"] for row in json.loads((video.HERE / "hd_plan.json").read_text())]
        with tempfile.TemporaryDirectory() as tmp, patch.object(video, "HD_DIR", Path(tmp)), \
                patch.object(video, "ColabPool") as pool, patch.object(video.hooks, "after_render"), \
                patch.object(sys, "argv", ["stageC_scout_p3.py", "--hd"]):
            run = pool.return_value.__enter__.return_value.run
            run.return_value = ({}, {})
            video.main()
            batch = run.call_args.args[0]
            self.assertEqual([job[0] for job in batch], plan_ids)
            redo = {job[0]: job for job in video.redo_jobs()}
            for job in batch:
                if job[0] in redo:
                    self.assertEqual(job, redo[job[0]])
                (Path(tmp) / f"clip_{job[0]}.mp4").touch()
            pool.reset_mock()
            video.main()
            pool.assert_not_called()

    def test_retake_only_publishes_requested_lines_and_keeps_first_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio"
            audio.mkdir()
            needed_actors = {line[1] for line in voices.RETAKES}
            for actor in voices.ACTORS:
                (audio / f"actor_{actor}.wav").write_bytes(b"original reference")
            (audio / "liang_8j_b.wav").write_bytes(b"first take")
            returned = [f"{line[0]}.{ext}" for line in voices.RETAKES for ext in ("wav", "mp3")]
            with tarfile.open(root / "vox_p3_retake_out.tar.gz", "w:gz") as archive:
                for name in [*returned, "actor_han.wav"]:
                    item = tarfile.TarInfo(name)
                    item.size = 4
                    archive.addfile(item, io.BytesIO(b"take"))
            with patch.multiple(voices, HERE=root, AUD=audio, JOB=root / "job.json"), \
                    patch.object(voices, "ColabPool") as pool, patch.dict(sys.modules, remote_job=Mock()), \
                    patch.object(sys, "argv", ["stageA_voices_p3.py", "--retake"]):
                pool.return_value.__enter__.return_value.run.return_value = ({}, {})
                voices.main()
                voices.main()
            job = json.loads((root / "job.json").read_text())
            self.assertEqual(set(job["actors"]), needed_actors)
            self.assertEqual(set(job["refs"]), needed_actors)
            self.assertEqual((audio / "actor_han.wav").read_bytes(), b"original reference")
            self.assertEqual((audio / "_v1/liang_8j_b.wav").read_bytes(), b"first take")
            for name in returned:
                self.assertEqual((audio / name).read_bytes(), b"take")


if __name__ == "__main__":
    unittest.main()
