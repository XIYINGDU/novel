#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
# -*- coding: utf-8 -*-
"""Stage D launcher: Run ByteDance LatentSync-1.6 (512x512) for ep01_p2 on one G4."""

import os
import shutil
import sys
import tarfile
import tempfile
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

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent / "common"))
from colab_pool import ColabPool
from lipsync_cache import publish_archive, upload_sources
from remote_job import run_remote

TAR_IN = BASE_DIR / "lipsync_in.tar.gz"
REMOTE_PY = BASE_DIR / "remote_latentsync_p2.py"
TAR_OUT = BASE_DIR / "lipsync_out.tar.gz"
OUT_DIR = BASE_DIR / "lipsync_out"


def main():
    if not TAR_IN.is_file():
        raise FileNotFoundError(f"Missing {TAR_IN}; run build_ep01_p2.py prepare first.")
    with tempfile.TemporaryDirectory(dir=BASE_DIR) as tmp:
        # A concurrent prepare must not change the input between verification and upload.
        upload = Path(tmp) / TAR_IN.name
        shutil.copyfile(TAR_IN, upload)
        with tarfile.open(upload, "r:gz") as tf:
            sids = [m.name[4:-4] for m in tf if m.isfile() and m.name.startswith("vid_") and m.name.endswith(".mp4")]
        if not sids:
            raise ValueError(f"No video inputs in {TAR_IN}")
        sources = upload_sources(upload, BASE_DIR / "lipsync_in", sids)
        download = Path(tmp) / TAR_OUT.name
        with ColabPool(n=1, seg="p2", stage="lipsync") as pool:
            _, failed = pool.run([("p2",)], lambda worker, _: run_remote(
                worker, REMOTE_PY, {upload: "/content/lipsync_in.tar.gz"},
                "/content/lipsync_out.tar.gz", download, timeout_s=1500, tag="lipsync"))
        if failed:
            raise SystemExit(f"P2 口型失败：{failed}")
        OUT_DIR.mkdir(exist_ok=True)
        publish_archive(download, OUT_DIR, sources)
        download.replace(TAR_OUT)
        print(f"[extract ok] {len(sids)} synced clips -> {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
