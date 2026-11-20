import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ep01_fix"))
import fix_1119 as fix


class RepairCacheTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.ref = root / "ref" / "k_liang_studio.png"
        self.ref.parent.mkdir()
        self.ref.write_bytes(b"reference")
        self.p3 = root / "ep01_p3"
        self.stills = self.p3 / "stills" / "fix1119"
        self.picks = root / "picks.json"
        self.set_pick(1)
        self.calls = []
        self.fail = set()

        def make_pool(**options):
            test = self

            class Pool:
                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    pass

                def run(self, jobs, work, key):
                    test.calls.append((options["seg"], options["stage"], options["n"], len(jobs)))
                    done, failed = {}, {}
                    for job in jobs:
                        name = key(job)
                        if name in test.fail:
                            failed[name] = "模拟失败"
                        else:
                            done[name] = work(None, job)
                    return done, failed

            return Pool()

        def draw(_worker, job):
            job["out"].write_bytes(job["ref"].read_bytes() + str(job["seed"]).encode())
            return job["out"]

        def render(_worker, job, size, folder, tag):
            dst = folder / f"clip_{job[0]}.mp4"
            dst.write_bytes(job[2].read_bytes() + str(job[5]).encode())
            return dst

        for replacement in (
            patch.multiple(fix, VID=root, REF=self.ref.parent, P3=self.p3, P3S=self.stills.parent,
                           FIX_STILLS=self.stills, PICKS=self.picks, ColabPool=make_pool),
            patch.object(fix.qwen, "render_job", side_effect=draw),
            patch.object(fix.wan, "render", side_effect=render),
            patch.object(fix.hooks, "after_render"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)

    def set_pick(self, k):
        self.picks.write_text(json.dumps({"8i1_start": str(self.stills / f"8i1_start_k{k}.png"),
                                          "8i1": "clip_s8i1_s1"}))

    def test_partial_rebuild_after_pick_change(self):
        fix.run_stills()
        fix.run_stills()
        fix.run_wan(2)
        fix.run_wan(2)
        self.assertEqual(self.calls, [("p3", "stills_fix", 1, 2), ("p3", "hd", 2, 4)])
        self.set_pick(2)
        with self.assertRaises(SystemExit):
            fix.run_cont()
        self.fail = {"clip_s8i1_s3", "clip_s8i1_s4"}
        with self.assertRaises(SystemExit):
            fix.run_wan(2)
        clips = self.p3 / "clips"
        self.assertEqual(sorted(p.stem for p in clips.glob("*.mp4")), ["clip_s8i1_s1", "clip_s8i1_s2"])
        self.fail.clear()
        fix.run_wan(2)
        self.assertEqual(self.calls[-1], ("p3", "hd", 2, 2))
        keyframe = (self.stills / "8i1_start_k2.png").read_bytes()
        self.assertTrue(all(p.read_bytes().startswith(keyframe) for p in clips.glob("*.mp4")))
        (clips / "clip_s8i1_s1.mp4").write_bytes(b"interrupted download")
        fix.run_wan(2)
        self.assertEqual(self.calls[-1], ("p3", "hd", 1, 1))

    def test_still_failures_and_changed_source(self):
        self.fail = {"8i1_start_k1", "8i1_start_k2"}
        with self.assertRaises(SystemExit):
            fix.run_stills()
        self.fail.clear()
        fix.run_stills()
        self.ref.write_bytes(b"new photo")
        fix.run_stills()
        self.assertEqual(self.calls[-1], ("p3", "stills_fix", 1, 2))
        self.assertTrue((self.stills / "8i1_start_k1.png").read_bytes().startswith(b"new photo"))
        changed = [dict(fix.STILLS[0], prompt="New camera angle"), fix.STILLS[1]]
        with patch.object(fix, "STILLS", changed):
            fix.run_stills()
        self.assertEqual(self.calls[-1], ("p3", "stills_fix", 1, 1))

    @unittest.skipUnless(shutil.which("ffmpeg"), "需要 ffmpeg 取续段首帧")
    def test_continuation_failure_then_cached_retry(self):
        movie = self.p3.parent / "fixture.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=32x32:r=16:d=1",
                        "-c:v", "libx264", str(movie)], check=True)
        fix.run_stills()
        def copy_movie(_worker, job, size, folder, tag):
            return Path(shutil.copyfile(movie, folder / f"clip_{job[0]}.mp4"))

        with patch.object(fix.wan, "render", side_effect=copy_movie):
            fix.run_wan(2)
        self.fail = {"clip_s8i1_s1_c1"}
        with self.assertRaises(SystemExit):
            fix.run_cont()
        self.fail.clear()
        fix.run_cont()
        count = len(self.calls)
        fix.run_cont()
        self.assertEqual(len(self.calls), count)
        self.assertEqual(self.calls[-1], ("p3", "cont", 1, 1))


if __name__ == "__main__":
    unittest.main()
