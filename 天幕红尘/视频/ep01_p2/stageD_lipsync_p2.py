#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
# -*- coding: utf-8 -*-
"""Stage D launcher: Run ByteDance LatentSync-1.6 (512x512) for ep01_p2 on G4 GPU and stop_all."""

import os
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

try:
    proxies = urllib.request.getproxies()
    for k in ("http", "https"):
        if k in proxies and proxies[k]:
            os.environ.setdefault(f"{k}_proxy", proxies[k])
            os.environ.setdefault(f"{k.upper()}_PROXY", proxies[k])
except Exception:
    pass

from colab_cli.common import state
from colab_cli.contents import ContentsClient
from colab_cli.runtime import ColabRuntime

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE_SCRIPT = "/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"

BASE_DIR = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/ep01_p2")
TAR_IN = BASE_DIR / "lipsync_in.tar.gz"
REMOTE_PY = BASE_DIR / "remote_latentsync_p2.py"
TAR_OUT = BASE_DIR / "lipsync_out.tar.gz"
OUT_DIR = BASE_DIR / "lipsync_out"


def run_bridge(*args) -> str:
    p = subprocess.run([BRIDGE_PY, BRIDGE_SCRIPT, *args], capture_output=True, text=True)
    return (p.stdout or "") + "\n" + (p.stderr or "")


def main():
    if not TAR_IN.exists():
        raise FileNotFoundError(f"Missing {TAR_IN}; run build_ep01_p2.py prepare first.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stop_ka = threading.Event()

    def keepalive_loop():
        while not stop_ka.wait(75.0):
            try:
                out = run_bridge("keepalive").strip()
                last = out.splitlines()[-1] if out else "ok"
                print(f"[keepalive] {last}", flush=True)
            except Exception as e:
                print(f"[keepalive warn] {e}", flush=True)

    try:
        print("[1/5] Waking fresh G4 GPU for LatentSync-1.6 Stage D...", flush=True)
        w_out = run_bridge("wake", "--gpu", "G4")
        print(w_out, flush=True)
        if "WAKE_URL:" not in w_out and not re.search(r"https://[a-zA-Z0-9.-]+\.gradio\.live", w_out):
            raise RuntimeError(f"Wake failed: {w_out}")

        threading.Thread(target=keepalive_loop, daemon=True).start()

        state._sessions = None
        sessions = state.store.list()
        if not sessions:
            raise RuntimeError("No active session found in colab-cli store after wake")
        sess = sessions.get("easycolab") or list(sessions.values())[0]
        contents = ContentsClient(sess)

        print("[2/5] Uploading lipsync_in.tar.gz & remote_latentsync_p2.py...", flush=True)
        for attempt in range(4):
            try:
                contents.upload(str(TAR_IN), "content/lipsync_in.tar.gz")
                contents.upload(str(REMOTE_PY), "content/remote_latentsync_p2.py")
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"  [upload retry {attempt + 1}] {e}", flush=True)
                time.sleep(3.0)

        print("[3/5] Launching detached LatentSync-1.6 (512x512) worker...", flush=True)
        launch_code = r"""
import os, subprocess, sys
for fn in ("/content/lipsync.log", "/content/lipsync.rc", "/content/lipsync_out.tar.gz"):
    if os.path.exists(fn):
        os.remove(fn)
cmd = f"{sys.executable} -u /content/remote_latentsync_p2.py > /content/lipsync.log 2>&1; echo $? > /content/lipsync.rc"
subprocess.Popen(["bash", "-lc", cmd], start_new_session=True)
print("LAUNCHED_OK", flush=True)
"""
        rt = ColabRuntime(
            sess.url, sess.token, session_name=sess.name, history=state.history,
            kernel_id=sess.kernel_id, session_id=sess.session_id,
        )
        try:
            outs = rt.execute_code(launch_code, allow_stdin=False, timeout=30)
            for o in outs:
                if "text" in o:
                    print(o["text"].strip(), flush=True)
                elif o.get("output_type") == "error":
                    raise RuntimeError(f"Kernel launch error: {o.get('evalue')}")
        finally:
            try:
                rt.stop(shutdown_kernel=False)
            except Exception:
                pass

        printed_len = 0
        t_start = time.time()
        with tempfile.TemporaryDirectory() as tmpd:
            local_log = Path(tmpd) / "lipsync.log"
            local_rc = Path(tmpd) / "lipsync.rc"
            while True:
                if time.time() - t_start > 1500:
                    raise TimeoutError("LatentSync worker timed out after 1500s")
                time.sleep(6.0)
                state._sessions = None
                cur_s = state.store.list().get(sess.name)
                if cur_s:
                    contents = ContentsClient(cur_s)
                try:
                    contents.download("content/lipsync.log", str(local_log))
                    txt = local_log.read_text(encoding="utf-8", errors="replace")
                    if len(txt) > printed_len:
                        sys.stdout.write(txt[printed_len:])
                        sys.stdout.flush()
                        printed_len = len(txt)
                except Exception:
                    pass
                try:
                    contents.download("content/lipsync.rc", str(local_rc))
                    rc_str = local_rc.read_text(encoding="utf-8", errors="replace").strip()
                    if rc_str != "":
                        try:
                            contents.download("content/lipsync.log", str(local_log))
                            txt = local_log.read_text(encoding="utf-8", errors="replace")
                            if len(txt) > printed_len:
                                sys.stdout.write(txt[printed_len:])
                                sys.stdout.flush()
                        except Exception:
                            pass
                        rc = int(rc_str)
                        print(f"\n[worker finished] exit_code={rc} ({time.time() - t_start:.1f}s)", flush=True)
                        if rc != 0:
                            raise RuntimeError(f"remote_latentsync_p2.py failed with exit code {rc}")
                        break
                except FileNotFoundError:
                    pass

        print("[4/5] Downloading /content/lipsync_out.tar.gz...", flush=True)
        for attempt in range(4):
            try:
                contents.download("content/lipsync_out.tar.gz", str(TAR_OUT))
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"  [download retry {attempt + 1}] {e}", flush=True)
                time.sleep(3.0)

        with tarfile.open(TAR_OUT, "r:gz") as tf:
            tf.extractall(OUT_DIR)
        extracted = sorted(p.name for p in OUT_DIR.glob("sync_*.mp4"))
        print(f"[extract ok] {len(extracted)} synced clips -> {extracted}", flush=True)
    finally:
        stop_ka.set()
        print("[5/5] IMMEDIATELY stopping all Colab GPUs (stop_all)...", flush=True)
        for attempt in range(4):
            out = run_bridge("stop_all")
            print(out, flush=True)
            if '"ok": true' in out and '"burn_rate_hourly": 0.0' in out:
                break
            time.sleep(3.0 * (attempt + 1))
        print("[auth_status]", run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
