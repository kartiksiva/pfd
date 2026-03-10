import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def _safe_job_key(video_path: str) -> str:
    stem = Path(video_path).stem or "video"
    return "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_"})[:40] or "video"


def extract_key_frame_images(
    *,
    video_path: str,
    key_frames: List[Dict],
    max_images: int = 12,
    output_root: Optional[Path] = None,
) -> List[Dict]:
    if not video_path or not os.path.exists(video_path) or not key_frames:
        return []

    output_root = output_root or Path("/tmp/pfcd_keyframes")
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
            if target.exists():
                extracted.append(
                    {
                        "path": str(target),
                        "timestamp_seconds": ts,
                        "reason": str(frame.get("reason", "baseline")),
                    }
                )
        except Exception:
            continue
    return extracted
