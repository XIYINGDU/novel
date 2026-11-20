"""Bind LatentSync outputs to the exact video and dry voice used to produce them."""
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path


def file_sha256(path):
    with path.open("rb") as f:
        return stream_sha256(f)


def stream_sha256(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
    return h.hexdigest()


def fingerprint(parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_stamp(path):
    p = path.with_suffix(".sha256")
    try:
        data = json.loads(p.read_text())
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError):
        return {"invalid": True}
    if not isinstance(data, dict) or not data.get("source") or not data.get("video"):
        return {"invalid": True}
    return data


def write_stamp(path, data):
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as f:
        json.dump(data, f, sort_keys=True)
    Path(f.name).replace(path.with_suffix(".sha256"))


def pair_key(input_dir, sid, video_hash, stem_hash):
    stamp = read_stamp(input_dir / f"vid_{sid}.mp4")
    if not stamp:  # An older prepare, or a combined/zoomed video from merge.
        return fingerprint([video_hash, stem_hash])
    if (stamp.get("video"), stamp.get("stem")) != (video_hash, stem_hash):
        raise ValueError(f"{sid} 的口型准备文件与记录不符，请重新 prepare")
    return stamp["source"]


def input_key(input_dir, sid):
    return pair_key(input_dir, sid, file_sha256(input_dir / f"vid_{sid}.mp4"),
                    file_sha256(input_dir / f"stem_{sid}.wav"))


def upload_sources(archive: Path, input_dir: Path, sids: list[str], *, merged: bool = False) -> dict[str, str]:
    # Hash the snapshot being uploaded, even if a new prepare has since started.
    if not merged:
        for sid in sids:
            if not read_stamp(input_dir / f"vid_{sid}.mp4"):
                raise ValueError(f"{sid} 的旧口型输入缺少来源记录，请先重新 prepare")
    with tarfile.open(archive) as tf:
        return {sid: pair_key(input_dir, sid, stream_sha256(tf.extractfile(f"vid_{sid}.mp4")),
                              stream_sha256(tf.extractfile(f"stem_{sid}.wav"))) for sid in sids}


def matches_output(path, source):
    return path.exists() and read_stamp(path) == {"source": source, "video": file_sha256(path)}


def record_output(path, source):
    write_stamp(path, {"source": source, "video": file_sha256(path)})


def publish_archive(archive: Path, output_dir: Path, sources: dict[str, str]):
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tf, tempfile.TemporaryDirectory(dir=output_dir) as td:
        for sid in sources:
            name = f"sync_{sid}.mp4"
            member = tf.getmember(name)
            if not member.isfile() or not member.size:
                raise ValueError(f"{name} 缺少视频内容")
            with tf.extractfile(member) as src, (Path(td) / name).open("wb") as dst:
                shutil.copyfileobj(src, dst)
        for sid, source in sources.items():
            dest = output_dir / f"sync_{sid}.mp4"
            tmp = Path(td) / dest.name
            record_output(tmp, source)
            tmp.replace(dest)
            tmp.with_suffix(".sha256").replace(dest.with_suffix(".sha256"))
            dest.with_suffix(".prekeep.mp4").unlink(missing_ok=True)
            dest.with_suffix(".prekeep.sha256").unlink(missing_ok=True)
