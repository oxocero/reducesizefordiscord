#!/usr/bin/env python3
"""
reencode_to_9mb.py
Encode a video so the output is ~9 MB.

Dependencies
------------
* ffmpeg  (4.x or later)
* ffprobe (usually ships with ffmpeg)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_duration(path: Path) -> float:
    """Return video duration in seconds (float) using ffprobe."""
    probe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    out = subprocess.run(probe_cmd, capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def reencode(
    src: Path,
    dst: Path,
    target_mb: float = 9.0,
    audio_kbps: int = 96,
    codec: str = "libx265",
):
    dur = get_duration(src)

    # Bytes → bits, then divide by duration   (1 MB = 1 048 576 bytes)
    bits_total = target_mb * 1024 * 1024 * 8
    aud_bps   = audio_kbps * 1000
    vid_bps   = max(bits_total / dur - aud_bps, 100_000)  # floor at 100 kbps
    vid_kbps  = int(vid_bps / 1000)

    print(
        f"[info] duration={dur:.2f}s | overall target={bits_total/1e6:.2f} Mb | "
        f"video={vid_kbps} kbps | audio={audio_kbps} kbps"
    )

    ff_cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-c:v", codec,
        "-b:v", f"{vid_kbps}k",
        "-maxrate", f"{vid_kbps}k",
        "-bufsize", f"{vid_kbps*2}k",
        "-c:a", "aac",
        "-b:a", f"{audio_kbps}k",
        "-movflags", "+faststart",  # stream-friendly MP4
        str(dst),
    ]

    print(" ".join(ff_cmd), "\n")
    subprocess.run(ff_cmd, check=True)
    final = dst.stat().st_size / (1024 * 1024)
    print(f"[done] output size: {final:.2f} MB → {dst}")


def main():
    p = argparse.ArgumentParser(
        description="Re-encode video to ≈ N MB with ffmpeg."
    )
    p.add_argument("input",  type=Path, help="source video file")
    p.add_argument("output", type=Path, help="destination file (e.g. out.mp4)")
    p.add_argument("--size",       type=float, default=9.0,
                   help="target size in MB (default 9)")
    p.add_argument("--audio-kbps", type=int,   default=96,
                   help="audio bitrate kbps (default 96)")
    p.add_argument("--codec", choices=["libx265", "libx264"],
                   default="libx265", help="video codec (default H.265)")
    args = p.parse_args()

    try:
        reencode(args.input, args.output, args.size, args.audio_kbps, args.codec)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
