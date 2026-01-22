#!/usr/bin/env python3
"""
reducesizefordiscord.py
Encode a video so the output fits under a target size (default ~9.8 MB).

Features
--------
* Two-pass encoding for optimal bitrate allocation
* Auto-downscaling for long/low-bitrate videos
* Container overhead compensation
* Configurable encoder preset

Dependencies
------------
* ffmpeg  (4.x or later)
* ffprobe (usually ships with ffmpeg)
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


# Container overhead factor (MP4 headers, metadata, etc.)
CONTAINER_OVERHEAD = 0.98


def get_video_info(path: Path) -> dict:
    """Return video duration, width, and height using ffprobe."""
    probe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json",
        str(path),
    ]
    out = subprocess.run(probe_cmd, capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    return {
        "duration": float(data["format"]["duration"]),
        "width": int(data["streams"][0]["width"]),
        "height": int(data["streams"][0]["height"]),
    }


def calculate_target_resolution(
    width: int,
    height: int,
    vid_kbps: int,
    min_kbps_for_1080p: int = 1500,
    min_kbps_for_720p: int = 600,
) -> tuple[int, int] | None:
    """
    Determine if downscaling is beneficial based on available bitrate.
    Returns (width, height) or None if no scaling needed.
    """
    # Determine current resolution tier
    current_height = min(width, height) if width < height else height

    if vid_kbps < min_kbps_for_720p and current_height > 480:
        # Scale to 480p
        target_height = 480
    elif vid_kbps < min_kbps_for_1080p and current_height > 720:
        # Scale to 720p
        target_height = 720
    else:
        return None

    # Calculate new dimensions maintaining aspect ratio (must be divisible by 2)
    scale_factor = target_height / height
    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)
    # Ensure dimensions are divisible by 2 (required by most codecs)
    new_width = new_width - (new_width % 2)
    new_height = new_height - (new_height % 2)

    return (new_width, new_height)


def reencode(
    src: Path,
    dst: Path,
    target_mb: float = 9.8,
    audio_kbps: int = 96,
    codec: str = "libx265",
    preset: str = "slow",
    auto_scale: bool = True,
):
    info = get_video_info(src)
    dur = info["duration"]
    width = info["width"]
    height = info["height"]

    # Account for container overhead
    effective_mb = target_mb * CONTAINER_OVERHEAD

    # Bytes → bits, then divide by duration
    bits_total = effective_mb * 1024 * 1024 * 8
    aud_bps = audio_kbps * 1000
    vid_bps = max(bits_total / dur - aud_bps, 100_000)  # floor at 100 kbps
    vid_kbps = int(vid_bps / 1000)

    # Determine if we should downscale
    scale_params = []
    target_res = None
    if auto_scale:
        target_res = calculate_target_resolution(width, height, vid_kbps)
        if target_res:
            scale_params = ["-vf", f"scale={target_res[0]}:{target_res[1]}"]

    res_str = f"{target_res[0]}x{target_res[1]}" if target_res else f"{width}x{height} (original)"

    print(
        f"[info] duration={dur:.2f}s | target={target_mb:.1f} MB (effective={effective_mb:.2f} MB)\n"
        f"[info] video={vid_kbps} kbps | audio={audio_kbps} kbps | resolution={res_str}\n"
        f"[info] codec={codec} | preset={preset} | two-pass=yes"
    )

    # Base ffmpeg arguments
    base_args = [
        "-i", str(src),
        "-c:v", codec,
        "-b:v", f"{vid_kbps}k",
        "-preset", preset,
    ]

    # Add scale filter if needed
    if scale_params:
        base_args.extend(scale_params)

    # Use a temporary directory for the two-pass log files
    with tempfile.TemporaryDirectory() as tmpdir:
        passlog = Path(tmpdir) / "ffmpeg2pass"

        # Pass 1: Analysis (no audio, output to null)
        print("\n[pass 1/2] Analysing video...")
        pass1_cmd = [
            "ffmpeg", "-y",
            *base_args,
            "-pass", "1",
            "-passlogfile", str(passlog),
            "-an",  # No audio for first pass
            "-f", "null",
            "NUL" if sys.platform == "win32" else "/dev/null",
        ]
        subprocess.run(pass1_cmd, check=True)

        # Pass 2: Actual encode with audio
        print("\n[pass 2/2] Encoding final output...")
        pass2_cmd = [
            "ffmpeg", "-y",
            *base_args,
            "-pass", "2",
            "-passlogfile", str(passlog),
            "-c:a", "aac",
            "-b:a", f"{audio_kbps}k",
            "-movflags", "+faststart",
            str(dst),
        ]
        subprocess.run(pass2_cmd, check=True)

    final_size = dst.stat().st_size / (1024 * 1024)
    status = "✓" if final_size <= target_mb else "⚠ over target"
    print(f"\n[done] output size: {final_size:.2f} MB ({status}) → {dst}")


def main():
    p = argparse.ArgumentParser(
        description="Re-encode video to fit under a target size with maximum quality."
    )
    p.add_argument("input", type=Path, help="source video file")
    p.add_argument("output", type=Path, help="destination file (e.g. out.mp4)")
    p.add_argument(
        "--size", type=float, default=9.8,
        help="target size in MB (default 9.8, safe for 10 MB limit)"
    )
    p.add_argument(
        "--audio-kbps", type=int, default=96,
        help="audio bitrate in kbps (default 96)"
    )
    p.add_argument(
        "--codec", choices=["libx265", "libx264"],
        default="libx265",
        help="video codec (default libx265/H.265)"
    )
    p.add_argument(
        "--preset",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast",
                 "medium", "slow", "slower", "veryslow"],
        default="slow",
        help="encoder preset - slower = better quality (default slow)"
    )
    p.add_argument(
        "--no-auto-scale", action="store_true",
        help="disable automatic downscaling for low-bitrate encodes"
    )
    args = p.parse_args()

    try:
        reencode(
            args.input,
            args.output,
            args.size,
            args.audio_kbps,
            args.codec,
            args.preset,
            auto_scale=not args.no_auto_scale,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
