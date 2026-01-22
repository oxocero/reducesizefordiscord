# reducesizefordiscord

A Python script that re-encodes videos to fit under Discord's file size limit (10 MB for free users, 25/50 MB for Nitro) while maximising quality.

## Features

- **Two-pass encoding** — Analyses video complexity first, then allocates bits optimally for better quality
- **Auto-downscaling** — Automatically reduces resolution when bitrate is too low for sharp output
- **Container overhead compensation** — Accounts for MP4 headers to avoid exceeding the target size
- **Configurable encoder preset** — Trade encoding speed for quality (defaults to `slow`)
- **H.265 by default** — Better compression than H.264 at the same quality

## Requirements

- Python 3.10+
- ffmpeg 4.x or later (with ffprobe)

### Installing ffmpeg

**Windows (winget):**
```bash
winget install ffmpeg
```

**Windows (Chocolatey):**
```bash
choco install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```

## Usage

Basic usage:
```bash
python reducesizefordiscord.py input.mp4 output.mp4
```

Specify a target size (e.g., 25 MB for Nitro):
```bash
python reducesizefordiscord.py input.mp4 output.mp4 --size 24.5
```

Maximum quality (slower encode):
```bash
python reducesizefordiscord.py input.mp4 output.mp4 --preset veryslow
```

Quick encode for previewing:
```bash
python reducesizefordiscord.py input.mp4 output.mp4 --preset fast
```

Use H.264 instead of H.265 (better compatibility):
```bash
python reducesizefordiscord.py input.mp4 output.mp4 --codec libx264
```

Disable automatic resolution scaling:
```bash
python reducesizefordiscord.py input.mp4 output.mp4 --no-auto-scale
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--size` | 9.8 | Target file size in MB |
| `--audio-kbps` | 96 | Audio bitrate in kbps |
| `--codec` | libx265 | Video codec (`libx265` or `libx264`) |
| `--preset` | slow | Encoder preset (`ultrafast` to `veryslow`) |
| `--no-auto-scale` | off | Disable automatic downscaling |

## How it works

1. Probes the source video for duration and resolution
2. Calculates the required video bitrate based on target size, duration, and audio bitrate
3. Determines if downscaling would improve quality (based on available bitrate)
4. Runs a two-pass encode: first pass analyses, second pass encodes
5. Outputs a stream-friendly MP4 with `faststart` enabled
