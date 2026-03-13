import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def _is_valid_image(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        size = path.stat().st_size
        if size < 16:
            return False
        head = path.read_bytes()[:12]
    except Exception:
        return False
    # JPEG, PNG, GIF, WEBP signatures.
    if head[:3] == b"\xff\xd8\xff":
        return True
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if head[:6] in {b"GIF87a", b"GIF89a"}:
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    return False


def _safe_job_key(video_path: str) -> str:
    stem = Path(video_path).stem or "video"
    return "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_"})[:40] or "video"


def _default_output_root(video_path: str) -> Path:
    video = Path(video_path)
    parent = video.parent
    if parent.name == "inputs":
        return parent.parent / "keyframes"
    return parent / "keyframes"


def extract_key_frame_images(
    *,
    video_path: str,
    key_frames: List[Dict],
    max_images: int = 12,
    output_root: Optional[Path] = None,
) -> List[Dict]:
    if not video_path or not os.path.exists(video_path) or not key_frames:
        return []

    output_root = output_root or _default_output_root(video_path)
    output_dir = output_root / _safe_job_key(video_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted: List[Dict] = []
    for idx, frame in enumerate(key_frames[:max_images], start=1):
        ts = float(frame.get("timestamp_seconds", 0.0) or 0.0)
        target = output_dir / f"frame_{idx:03d}_{int(ts * 1000)}.jpg"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(max(ts, 0.0)),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(target),
        ]
        try:
            subprocess.run(command, capture_output=True, check=True, timeout=15)
            if _is_valid_image(target):
                extracted.append(
                    {
                        "path": str(target.resolve()),
                        "timestamp_seconds": ts,
                        "reason": str(frame.get("reason", "baseline")),
                    }
                )
            elif target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass
        except Exception:
            continue
    return extracted
