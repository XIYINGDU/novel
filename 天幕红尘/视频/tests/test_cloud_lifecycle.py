import contextlib
import io
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
import colab_pool
import qwen


class FakeBridge:
    def __init__(self):
        self.active = {"another-pool-w1"}
        self.stop_fails = False
        self.status_fails = False
        self.stopped = []

    def __call__(self, command, *args, timeout=900):
        if command == "wake":
            self.active.add(args[-1])
            return "https://example.gradio.live"
        if command == "auth_status":
            if self.status_fails:
                return '{"ok": false, "error": "offline"}'
            return json.dumps({"ok": True, "logged_in": True, "active_assignments": len(self.active),
                               "sessions": [{"name": name, "endpoint": f"ep-{name}"} for name in self.active]})
        if command == "stop":
            name = args[-1]
            self.stopped.append(name)
            if self.stop_fails:
                return '{"ok": false, "error": "refused"}'
            self.active.discard(name)
            return json.dumps({"ok": True, "stopped": name, "endpoint": f"ep-{name}"})
        raise AssertionError(f"unexpected bridge command {command}")


class CloudLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.bridge = FakeBridge()
        self.enterContext(mock.patch.object(colab_pool, "bridge", self.bridge))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.record = self.enterContext(mock.patch.object(colab_pool.hooks, "record_run"))

    def test_shutdown_errors_retry_owned_session_and_propagate(self):
        pool = colab_pool.ColabPool(n=1)
        with self.assertRaisesRegex(RuntimeError, "无法核实"), mock.patch.object(colab_pool.time, "sleep"):
            with pool:
                self.bridge.status_fails = self.bridge.stop_fails = True
        self.assertEqual(self.bridge.stopped, [pool.workers[0].name] * 4)
        self.assertEqual(len(self.bridge.active), 2)
        self.assertIn("未核实", self.record.call_args.kwargs["note"])

    def test_verified_shutdown_preserves_other_pool(self):
        with colab_pool.ColabPool(n=1):
            pass
        self.assertEqual(self.bridge.active, {"another-pool-w1"})
        self.record.assert_called_once()

    def test_running_endpoint_is_detected_after_name_disappears(self):
        pool = colab_pool.ColabPool(n=1)
        def bridge(cmd, *args, timeout=900):
            result = self.bridge(cmd, *args, timeout=timeout)
            if cmd == "auth_status" and len(self.bridge.stopped) == 1:
                reply = json.loads(result)
                reply["sessions"].append({"name": "colab-vm", "endpoint": pool.workers[0].endpoint})
                reply["active_assignments"] += 1
                return json.dumps(reply)
            return result

        with mock.patch.object(colab_pool, "bridge", bridge), mock.patch.object(colab_pool.time, "sleep"):
            with pool:
                pass
        self.assertEqual(self.bridge.stopped, [pool.workers[0].name] * 2)

    def test_startup_time_is_charged_before_setup(self):
        pool = colab_pool.ColabPool(n=1, max_cu=2)
        clock = [1000.0]
        def bridge(cmd, *args, timeout=900):
            if cmd == "wake":
                self.assertAlmostEqual(timeout, 2 * 3600 / pool.rate)
                clock[0] += 720
            return self.bridge(cmd, *args, timeout=timeout)

        with mock.patch.object(colab_pool, "bridge", bridge), mock.patch.object(colab_pool.time, "time", lambda: clock[0]):
            with self.assertRaisesRegex(RuntimeError, "开机已达 CU 预算"), pool:
                self.fail("任务不应启动")
        self.assertAlmostEqual(self.record.call_args.args[6], 0.2)
        self.assertEqual(self.bridge.active, {"another-pool-w1"})

    def test_exit_waits_for_watchdog_before_recording(self):
        pool = colab_pool.ColabPool(n=1, max_cu=1, keepalive_s=0.01)
        stopping, allow_stop, inside_exit = threading.Event(), threading.Event(), threading.Event()
        def bridge(cmd, *args, timeout=900):
            if cmd == "stop":
                stopping.set()
                if not allow_stop.wait(3):
                    raise AssertionError("release was not resumed")
            return self.bridge(cmd, *args, timeout=timeout)

        def finish_job(w, job):
            if not stopping.wait(3):
                raise AssertionError("watchdog did not enter stop")
            return "completed"

        def run():
            with pool:
                pool.max_cu = 0
                pool.run([("shot",)], finish_job)
                inside_exit.set()

        with mock.patch.object(colab_pool, "bridge", bridge):
            thread = threading.Thread(target=run)
            thread.start()
            try:
                self.assertTrue(inside_exit.wait(3))
                thread.join(0.05)
                self.assertTrue(thread.is_alive())
                self.record.assert_not_called()
            finally:
                allow_stop.set()
                thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.record.call_args.args[3:5], (1, 0))
        self.assertTrue(pool.over_budget)
        self.assertEqual(self.bridge.active, {"another-pool-w1"})

    def test_incomplete_inventory_cannot_verify_release(self):
        replies = [
            {"ok": True, "logged_in": False},
            {"ok": True, "logged_in": True, "active_assignments": 1, "sessions": []},
        ]
        for reply in replies:
            with self.subTest(reply=reply), mock.patch.object(colab_pool, "bridge", return_value=json.dumps(reply)):
                with self.assertRaises(RuntimeError):
                    colab_pool.status()


class QwenSetupTests(unittest.TestCase):
    def test_model_stopped_or_stuck_after_load(self):
        for busy, error in [(False, RuntimeError), (True, TimeoutError)]:
            with self.subTest(busy=busy):
                clock = [0]
                def sleep(seconds):
                    clock[0] += seconds
                st = {"all_downloaded": True, "model_loaded": False, "is_loading_vram": busy,
                      "task_message": "加载失败" if not busy else "加载中"}
                worker = colab_pool.Worker("mock", "mock://")
                with (mock.patch.object(qwen, "http_json", return_value=st),
                      mock.patch.object(qwen.time, "sleep", sleep),
                      mock.patch.object(qwen.time, "monotonic", lambda: clock[0])):
                    with self.assertRaises(error):
                        qwen.setup(worker)
                self.assertLessEqual(clock[0], 900)


if __name__ == "__main__":
    unittest.main()
