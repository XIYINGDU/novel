# 21 号镜头 A/B 测试：IndexTTS2 配音 + InfiniteTalk 生成口型
# 用法（在 VM 上跑）：
#   /content/index-tts/.venv/bin/python /content/talk_test21.py tts
#   python /content/talk_test21.py video     （系统 python 即可，内部调用 InfiniteTalk 的 venv）
import sys, os, json, subprocess, asyncio
from pathlib import Path

W = Path("/content/test21"); W.mkdir(exist_ok=True)
LINE = "……吃了，妈。我就是……想听听您声音。"
REF_TEXT = "这批货我已经联系好了，下个礼拜就能到莫斯科，价钱的事咱们回头再慢慢谈。"
IMG = "/content/ref/罗家明.png"
stage = sys.argv[1] if len(sys.argv) > 1 else "all"

def log(m):
    print(m, flush=True)
    with open(W / "progress.log", "a") as f: f.write(m + "\n")

if stage in ("tts", "all"):
    # 1) 音色参考：用 edge-tts 的低沉男声生成一段参考音（以后可以换成真人录音）
    import edge_tts
    ref = W / "ref_voice.mp3"
    if not ref.exists():
        asyncio.run(edge_tts.Communicate(REF_TEXT, "zh-CN-YunjianNeural", rate="-10%", pitch="-8Hz").save(str(ref)))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ref), "-ar", "24000", "-ac", "1", str(W / "ref_voice.wav")], check=True)
    # 2) IndexTTS2：同一个音色，用文字描述情绪
    sys.path.insert(0, "/content/index-tts")
    os.chdir("/content/index-tts")
    from indextts.infer_v2 import IndexTTS2
    tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_fp16=True)
    variants = {
        "a": dict(emo_text="强忍着哭，声音发颤，压低声音，假装平静", use_emo_text=True, emo_alpha=0.7),
        "b": dict(emo_text="悲伤，哽咽，很轻很慢", use_emo_text=True, emo_alpha=0.9),
    }
    for k, kw in variants.items():
        out = W / f"line_{k}.wav"
        tts.infer(spk_audio_prompt=str(W / "ref_voice.wav"), text=LINE, output_path=str(out), **kw)
        log(f"tts {k} done {out}")
    log("TTS_DONE")

if stage in ("video", "all"):
    os.chdir("/content/InfiniteTalk")
    audio = str(W / "line_a.wav")
    # 前后各留 0.6 秒静音，让表演有起落
    padded = W / "line_a_pad.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio, "-af",
                    "adelay=600|600,apad=pad_dur=0.8", "-ar", "16000", str(padded)], check=True)
    spec = {
        "prompt": "A 42-year-old Chinese businessman in a white shirt and loosened red tie sits in a dim Moscow office "
                  "at midnight, holding a black telephone receiver to his ear. His eyes are red, he is holding back "
                  "tears and forcing a calm voice while talking to his mother, then wipes his eyes with his sleeve. "
                  "Cinematic 35mm film, warm desk lamp, film grain, realistic.",
        "cond_video": IMG,
        "cond_audio": {"person1": str(padded)},
    }
    jp = W / "spec.json"; jp.write_text(json.dumps(spec, ensure_ascii=False))
    cmd = ["/content/InfiniteTalk/.venv/bin/python", "generate_infinitetalk.py",
           "--ckpt_dir", "/content/InfiniteTalk_weights/Wan2.1-I2V-14B-480P",
           "--wav2vec_dir", "/content/InfiniteTalk_weights/chinese-wav2vec2-base",
           "--infinitetalk_dir", "/content/InfiniteTalk_weights/InfiniteTalk/single/infinitetalk.safetensors",
           "--input_json", str(jp), "--size", "infinitetalk-480", "--sample_steps", "40",
           "--mode", "streaming", "--motion_frame", "9", "--save_file", str(W / "shot21_infinitetalk")]
    log("video start: " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    (W / "video_stdout.log").write_text(r.stdout + "\n" + r.stderr)
    log(f"VIDEO_DONE rc={r.returncode}" if r.returncode == 0 else f"VIDEO_ERROR rc={r.returncode}")
