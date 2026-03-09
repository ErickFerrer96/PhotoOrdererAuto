# 📷 Photo Watermark Automation

> Automated date-stamp watermarking system for bulk photo processing — replicating Android-style timestamps with dynamic orientation-aware sizing.

---

## Overview

A Python automation tool that applies clean, legible date watermarks to hundreds of photos in batch. The system intelligently detects photo orientation and adjusts watermark proportions accordingly, ensuring consistent results across both portrait and landscape images.

---

## Features

- **Orientation-aware sizing** — automatically scales watermark to 80% for vertical photos, full size for horizontal
- **Android-style timestamps** — format: `07 February 2026 14:30`
- **Batch processing** — handles hundreds of photos without stopping on individual failures
- **Cross-platform font fallbacks** — works on Windows, macOS, and Linux
- **MyPy-compatible** — full static type annotations
- **Resilient error handling** — failed images are logged and skipped; processing continues

---

## Requirements

```
Python >= 3.9
Pillow
```
---

## Installation

```bash
git clone https://github.com/your-username/photo-watermark.git
cd photo-watermark
```

---

## Usage

```bash
python watermark.py --input ./photos --output ./output
```

### Options

| Argument | Description | Default |
|---|---|---|
| `--input` | Folder with source photos | `./photos` |
| `--output` | Destination folder for watermarked photos | `./output` |
| `--format` | Timestamp format string | `%d %B %Y %H:%M` |
| `--position` | Watermark position | `bottom-left` |

---

## Watermark Behavior

| Orientation | Scale | Position |
|---|---|---|
| Horizontal (landscape) | 100% | Bottom-left |
| Vertical (portrait) | 80% | Bottom-left |

The watermark reads the **EXIF `DateTimeOriginal`** field when available, falling back to the file's modification date.

---

## Font Resolution

The tool attempts to load fonts in the following priority order:

1. System fonts (platform-specific paths)
2. Bundled fallback font
3. Pillow default bitmap font

---
