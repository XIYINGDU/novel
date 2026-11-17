#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
# -*- coding: utf-8 -*-
"""Stage A launcher: Prepare voice refs, wake G4 GPU, synthesize Ep01 Part 2 VoxCPM2 dialogue, download, and stop_all."""

import os
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
BRIDGE = "/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
ROOT = VID_ROOT / "ep01_p2"
AUD_OUT = ROOT / "audio"
AUD_OUT.mkdir(parents=True, exist_ok=True)
REMOTE_PY = ROOT / "remote_voxcpm2_p2.py"
REFS_TAR_LOCAL = ROOT / "voice_refs_p2.tar.gz"
OUT_TAR_LOCAL = ROOT / "vox_ep01_p2_out.tar.gz"


def run_bridge(*args: str) -> str:
    res = subprocess.run([BRIDGE_PY, BRIDGE, *args], capture_output=True, text=True)
    return (res.stdout + res.stderr).strip()


def keepalive_loop(stop_evt: threading.Event):
    while not stop_evt.wait(70.0):
        try:
            out = run_bridge("keepalive")
            print(f"  [keepalive] {out}", flush=True)
        except Exception as e:
            print(f"  [keepalive err] {e}", flush=True)


def build_refs_tar():
    kug_mp3 = VID_ROOT / "v03_pilot" / "audio" / "line_05b2_en.mp3"
    su_mp3 = VID_ROOT / "v03_pilot" / "audio" / "su_continuous_2.mp3"
    with tempfile.TemporaryDirectory() as tmpd:
        td = Path(tmpd)
        kug_wav = td / "ref_kug_en.wav"
        su_wav = td / "ref_su.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(kug_mp3), "-ar", "44100", "-ac", "1", str(kug_wav)], check=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(su_mp3), "-ar", "44100", "-ac", "1", str(su_wav)], check=True)
        with tarfile.open(REFS_TAR_LOCAL, "w:gz") as tf:
            tf.add(kug_wav, arcname="ref_kug_en.wav")
            tf.add(su_wav, arcname="ref_su.wav")
    print(f"[prep] Built {REFS_TAR_LOCAL.name} ({REFS_TAR_LOCAL.stat().st_size // 1024} KB)", flush=True)


def main():
    build_refs_tar()
    stop_ka = threading.Event()
    try:
        print("[1/5] Waking EasyColab G4 GPU for VoxCPM2 Stage A...", flush=True)
        wake_out = run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")

        state._sessions = None
        sessions = state.store.list()
        if not sessions:
            raise RuntimeError("No Colab session found after wake")
        sess = sessions.get("easycolab") or next(iter(sessions.values()))
        contents = ContentsClient(sess)

        ka_thread = threading.Thread(target=keepalive_loop, args=(stop_ka,), daemon=True)
        ka_thread.start()

        print("[2/5] Uploading voice refs & remote_voxcpm2_p2.py...", flush=True)
        for src, dst in [(REFS_TAR_LOCAL, "content/voice_refs_p2.tar.gz"), (REMOTE_PY, "content/remote_voxcpm2_p2.py")]:
            for attempt in range(4):
                try:
                    contents.upload(str(src), dst)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    print(f"  [upload retry {attempt + 1}] {e}", flush=True)
                    time.sleep(3.0)

        print("[3/5] Launching detached VoxCPM2 Stage A worker...", flush=True)
        launch_code = r"""
import os, subprocess, sys
for fn in ("/content/vox_p2.log", "/content/vox_p2.rc", "/content/vox_ep01_p2_out.tar.gz"):
    if os.path.exists(fn):
        os.remove(fn)
cmd = f"{sys.executable} -u /content/remote_voxcpm2_p2.py > /content/vox_p2.log 2>&1; echo $? > /content/vox_p2.rc"
subprocess.Popen(["bash", "-lc", cmd], start_new_session=True)
print("VOX_P2_LAUNCHED_OK", flush=True)
"""
        rt = ColabRuntime(
            sess.url,
            sess.token,
            session_name=sess.name,
            history=state.history,
            kernel_id=sess.kernel_id,
            session_id=sess.session_id,
        )
        try:
            outs = rt.execute_code(launch_code, allow_stdin=False, timeout=30)
            for o in outs:
                if "text" in o:
                    print(o["text"].strip(), flush=True)
                elif o.get("output_type") == "error":
                    raise RuntimeError(f"Kernel error: {o.get('evalue')}")
        finally:
            try:
                rt.stop(shutdown_kernel=False)
            except Exception:
                pass

        printed_len = 0
        t_start = time.time()
        with tempfile.TemporaryDirectory() as tmpd:
            local_log = Path(tmpd) / "vox_p2.log"
            local_rc = Path(tmpd) / "vox_p2.rc"
            while True:
                if time.time() - t_start > 900:
                    raise TimeoutError("VoxCPM2 timed out after 900s")
                time.sleep(5.0)
                state._sessions = None
                cur_s = state.store.list().get(sess.name)
                if cur_s:
                    contents = ContentsClient(cur_s)
                try:
                    contents.download("content/vox_p2.log", str(local_log))
                    txt = local_log.read_text(encoding="utf-8", errors="replace")
                    if len(txt) > printed_len:
                        sys.stdout.write(txt[printed_len:])
                        sys.stdout.flush()
                        printed_len = len(txt)
                except Exception:
                    pass

                try:
                    contents.download("content/vox_p2.rc", str(local_rc))
                    rc_str = local_rc.read_text(encoding="utf-8", errors="replace").strip()
                    if rc_str != "":
                        try:
                            contents.download("content/vox_p2.log", str(local_log))
                            txt = local_log.read_text(encoding="utf-8", errors="replace")
                            if len(txt) > printed_len:
                                sys.stdout.write(txt[printed_len:])
                                sys.stdout.flush()
                        except Exception:
                            pass
                        rc = int(rc_str)
                        print(f"\n[worker finished] exit_code={rc} ({time.time() - t_start:.1f}s)", flush=True)
                        if rc != 0:
                            raise RuntimeError(f"remote_voxcpm2_p2.py failed with exit code {rc}")
                        break
                except FileNotFoundError:
                    pass

        print("[4/5] Downloading /content/vox_ep01_p2_out.tar.gz...", flush=True)
        for attempt in range(4):
            try:
                contents.download("content/vox_ep01_p2_out.tar.gz", str(OUT_TAR_LOCAL))
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"  [download retry {attempt + 1}] {e}", flush=True)
                time.sleep(3.0)

        with tarfile.open(OUT_TAR_LOCAL, "r:gz") as tf:
            tf.extractall(AUD_OUT)
        print(f"[extracted] {len(list(AUD_OUT.glob('*.mp3')))} mp3 files -> {AUD_OUT}", flush=True)
    finally:
        stop_ka.set()
        print("[5/5] Stopping EasyColab GPU (stop_all)...", flush=True)
        print(run_bridge("stop_all"), flush=True)
        print("[auth_status]", run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
