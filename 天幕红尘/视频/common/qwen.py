#!/usr/bin/env python3
"""Qwen-Image-2.1（EasyColab /minimax_api）共享调用。配合 colab_pool 使用：

    from colab_pool import ColabPool
    import qwen
    with ColabPool(n=1, setup=qwen.setup) as pool:
        pool.run(jobs, qwen.render_job, key=lambda j: str(j["out"]))

job: {"out": Path, "mode": "t2i"|"i2i_edit", "prompt", "neg", "seed", ["ref": Path], ["width","height","steps"]}
已存在且 >20KB 的 out 自动跳过。注意 P-SHM-NO-MIX：同一台机器不要再跑 Wan。
"""
from __future__ import annotations

import base64
import json
import time
import urllib.request
from pathlib import Path

MODEL = "qwen_image_21"
STYLE = ("1991 Kodak Vision 35mm cinema film still, anamorphic lens, natural skin texture, "
         "subtle film grain, realistic lighting, shallow depth of field, no subtitles, no watermarks.")
NEG_PORTRAIT = ("cartoon, anime, CGI, 3d render, oversaturated, plastic skin, extra person, multiple people, "
                "second head, photobomb edge, cropped neighbor, watermark, subtitle, text, deformed hands, "
                "extra fingers, modern smartphone")


def http_json(url: str, payload: dict | None = None, timeout: int = 60, retries: int = 5) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    hdrs = {"Content-Type": "application/json"} if payload is not None else {}
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data is not None else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last = e
            time.sleep(2.5 * (i + 1))
    raise last


def download(url: str, dst: Path, retries: int = 5):
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                dst.write_bytes(resp.read())
                return
        except Exception as e:
            last = e
            time.sleep(2.5 * (i + 1))
    raise last


def _wait_model(url: str, ready: str, busy: str, timeout: int) -> dict:
    deadline = time.monotonic() + timeout
    idle_since = None
    while time.monotonic() < deadline:
        time.sleep(4)
        st = http_json(url)
        if st.get(busy):
            idle_since = None
        elif st.get(ready):
            return st
        else:
            # 服务异步启动任务，磁盘状态缓存最多 12 秒。
            now = time.monotonic()
            if idle_since is None:
                idle_since = now
            elif now - idle_since >= 16:
                raise RuntimeError(f"Qwen {ready} 未就绪，任务已停止：{st.get('task_message')}")
    raise TimeoutError(f"等待 Qwen {ready} 超过 {timeout} 秒")


def setup(w):
    """下载并加载 Qwen-Image-2.1 到这台机器。"""
    base = w.base_gradio
    status_url = f"{base}/minimax_api/status?model_id={MODEL}"
    st = http_json(status_url)
    if not st.get("all_downloaded"):
        w.log("下载 Qwen 权重 ...")
        http_json(f"{base}/minimax_api/download_model", {"model_id": MODEL})
        st = _wait_model(status_url, "all_downloaded", "is_downloading", timeout=1800)
    if not st.get("model_loaded"):
        w.log("加载 Qwen 到显存 ...")
        http_json(f"{base}/minimax_api/load_model", {"model_id": MODEL, "precision_mode": "bf16", "offload_mode": "disk"})
        _wait_model(status_url, "model_loaded", "is_loading_vram", timeout=900)
    w.ctx["b64"] = {}
    w.log("Qwen 就绪")


def render_job(w, j: dict) -> Path:
    out = Path(j["out"])
    if out.exists() and out.stat().st_size > 20_000:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    base = w.base_gradio
    payload = {
        "model_id": MODEL, "task_mode": j.get("mode", "t2i"), "visual_prompt": j["prompt"],
        "negative_prompt": j.get("neg", NEG_PORTRAIT), "width": j.get("width", 1280), "height": j.get("height", 720),
        "num_inference_steps": j.get("steps", 30), "seed": j["seed"], "randomize_seed": False, "batch_count": 1,
    }
    if payload["task_mode"] == "i2i_edit":
        rp = Path(j["ref"])
        if rp not in w.ctx["b64"]:
            w.ctx["b64"][rp] = base64.b64encode(rp.read_bytes()).decode("ascii")
        payload["first_frame_base64"] = w.ctx["b64"][rp]
    t0 = time.time()
    jid = http_json(f"{base}/minimax_api/generate", payload)["job_id"]
    while True:
        time.sleep(2.0)
        st = http_json(f"{base}/minimax_api/job/{jid}")
        if st.get("status") == "completed":
            fn = st.get("filename") or Path(st["filepath"]).name
            download(f"{base}/minimax_api/media/{fn}", out)
            w.log(f"saved {out.name} ({out.stat().st_size // 1024} KB, {time.time() - t0:.0f}s)")
            return out
        if st.get("status") in ("failed", "error"):
            raise RuntimeError(f"Qwen job failed {out.name}: {st}")


# ---------- 关键帧：链式依赖分波次 + 双人合成参考 ----------
def composite(paths: list[Path], out: Path, h: int = 720) -> Path:
    """把多张定妆图横拼成一张，作为双人镜头的 i2i 参考（Qwen 一次只吃一张图）。需 pillow。"""
    from PIL import Image
    if out.exists():
        return out
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((int(im.width * h / im.height), h)) for im in ims]
    canvas = Image.new("RGB", (sum(im.width for im in ims), h), "white")
    x = 0
    for im in ims:
        canvas.paste(im, (x, 0))
        x += im.width
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def run_keyframes(pool, keyframes: list[dict], still_dir: Path) -> dict:
    """keyframes: {"id", "prompt", "seed", ["ref": Path] | ["ref_still_id": id], ["mode","neg"]}。
    ref_still_id 指向同批另一张关键帧（续接姿态/同机位），按依赖深度分波次，每波内多台并行。"""
    by_id = {k["id"]: k for k in keyframes}

    def depth(k, seen=()):
        p = k.get("ref_still_id")
        if not p:
            return 0
        if p in seen:
            raise ValueError(f"关键帧循环依赖：{k['id']} → {p}")
        if p not in by_id:  # 上游不在本批：必须已在磁盘上
            if not (still_dir / f"{p}.png").exists():
                raise ValueError(f"关键帧 {k['id']} 的上游 {p} 既不在本批也不在磁盘")
            return 0
        return 1 + depth(by_id[p], seen + (k["id"],))

    waves: dict[int, list] = {}
    for k in keyframes:
        waves.setdefault(depth(k), []).append(k)
    done, failed = {}, {}
    for d in sorted(waves):
        jobs = []
        for k in waves[d]:
            parent = k.get("ref_still_id")
            if parent and parent not in done and not (still_dir / f"{parent}.png").exists():
                failed[k["id"]] = f"上游 {parent} 未生成"
                continue
            ref = (still_dir / f"{parent}.png") if parent else k.get("ref")
            jobs.append({"out": still_dir / f"{k['id']}.png", "mode": k.get("mode", "i2i_edit" if ref else "t2i"),
                         "ref": ref, "seed": k["seed"], "prompt": k["prompt"], "neg": k.get("neg", NEG_PORTRAIT)})
        print(f"[keyframes] 第 {d + 1} 波：{len(jobs)} 张", flush=True)
        res, fl = pool.run(jobs, render_job, key=lambda j: j["out"].stem)
        done.update(res)
        failed.update(fl)
    return {"done": done, "failed": failed}
