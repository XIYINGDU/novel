#!/usr/bin/env python3
"""在 ColabPool 的某台机器上跑一个长脚本（后台执行、轮询日志、下载产物）。
必须用 google-colab-cli 的 python 运行（要 import colab_cli）：
  /Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python ...
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from colab_cli.common import state
from colab_cli.contents import ContentsClient
from colab_cli.runtime import ColabRuntime


def _session(name: str):
    state._sessions = None
    s = state.store.list().get(name)
    if not s:
        raise RuntimeError(f"找不到会话 {name}")
    return s


def _retry(fn, n=4, what=""):
    for i in range(n):
        try:
            return fn()
        except Exception as e:
            if i == n - 1:
                raise
            print(f"  [{what} retry {i + 1}] {e}", flush=True)
            time.sleep(3.0 * (i + 1))


def run_remote(worker, script: Path, uploads: dict[Path, str], out_remote: str, out_local: Path,
               timeout_s: int = 1800, tag: str = "job") -> Path:
    """uploads: {本地文件: '/content/xxx'}；script 上传为 /content/<名字> 后台执行；完成后下载 out_remote。"""
    sess = _session(worker.name)
    contents = ContentsClient(sess)
    for src, dst in {**uploads, Path(script): f"/content/{Path(script).name}"}.items():
        _retry(lambda: contents.upload(str(src), dst.lstrip("/")), what="upload")
    log, rc = f"/content/{tag}.log", f"/content/{tag}.rc"
    launch = (f"import os,subprocess,sys\n"
              f"for f in ({log!r},{rc!r},{out_remote!r}):\n    os.path.exists(f) and os.remove(f)\n"
              f"subprocess.Popen(['bash','-lc',f'{{sys.executable}} -u /content/{Path(script).name} > {log} 2>&1; echo $? > {rc}'],"
              f"start_new_session=True)\nprint('LAUNCHED',flush=True)\n")
    rt = ColabRuntime(sess.url, sess.token, session_name=sess.name, history=state.history,
                      kernel_id=sess.kernel_id, session_id=sess.session_id)
    try:
        for o in rt.execute_code(launch, allow_stdin=False, timeout=30):
            if o.get("output_type") == "error":
                raise RuntimeError(f"内核错误：{o.get('evalue')}")
    finally:
        try:
            rt.stop(shutdown_kernel=False)
        except Exception:
            pass
    worker.log(f"已在云端启动 {Path(script).name}")
    t0, shown = time.time(), 0
    with tempfile.TemporaryDirectory() as td:
        lp, rp = Path(td) / "log", Path(td) / "rc"
        while True:
            if time.time() - t0 > timeout_s:
                raise TimeoutError(f"{tag} 超时 {timeout_s}s")
            time.sleep(6.0)
            contents = ContentsClient(_session(worker.name))
            try:
                contents.download(log.lstrip("/"), str(lp))
                txt = lp.read_text(errors="replace")
                for line in txt[shown:].splitlines():
                    if "it/s]" not in line and line.strip():  # 去掉 tqdm 进度条噪音
                        worker.log(line)
                shown = len(txt)
            except Exception:
                pass
            try:
                contents.download(rc.lstrip("/"), str(rp))
                code = rp.read_text().strip()
            except Exception:
                code = ""
            if code:
                if int(code) != 0:
                    raise RuntimeError(f"{tag} 远端退出码 {code}")
                break
    out_local.parent.mkdir(parents=True, exist_ok=True)
    _retry(lambda: ContentsClient(_session(worker.name)).download(out_remote.lstrip("/"), str(out_local)), what="download")
    worker.log(f"产物已下载 {out_local.name}（{time.time() - t0:.0f}s）")
    return out_local
