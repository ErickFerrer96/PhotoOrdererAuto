from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps  # type: ignore[import-untyped]

from config import Config, PHOTO_PATTERNS


# ── Date extraction ────────────────────────────────────────────────────────────

# Tag IDs in priority order: DateTimeOriginal, DateTimeDigitized, DateTime
_EXIF_DATE_TAGS = (36867, 36868, 306)
_EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"

# (compiled pattern, strptime format for joined groups)
_FILENAME_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # IMG_20240115_143045  PXL_20240115_143045  VID_20240115_143045
    (re.compile(r"(?:IMG|PXL|VID|DSC)_(\d{8})_(\d{6})"), "%Y%m%d%H%M%S"),
    # Screenshot_2024-01-15-14-30-45  or  Screenshot_2024-01-15_14-30-45
    (re.compile(r"Screenshot_(\d{4})-(\d{2})-(\d{2})[_-](\d{2})[_-](\d{2})[_-](\d{2})"), "%Y%m%d%H%M%S"),
    # Screenshot_2024-01-15  (date only)
    (re.compile(r"Screenshot_(\d{4}-\d{2}-\d{2})"), "%Y-%m-%d"),
    # Generic YYYYMMDD_HHMMSS
    (re.compile(r"(\d{8})_(\d{6})"), "%Y%m%d%H%M%S"),
]


def _parse_exif_date(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value.strip(), _EXIF_DATE_FMT)
    except ValueError:
        return None


def _date_from_filename(image_path: str) -> Optional[datetime]:
    stem = Path(image_path).stem
    for pattern, fmt in _FILENAME_DATE_PATTERNS:
        m = pattern.search(stem)
        if m:
            try:
                return datetime.strptime("".join(m.groups()), fmt)
            except ValueError:
                continue
    return None


def get_photo_date(image_path: str) -> datetime:
    try:
        img = Image.open(image_path)

        # Modern getexif() API
        try:
            exif = img.getexif()
            for tag_id in _EXIF_DATE_TAGS:
                value = exif.get(tag_id)
                if value:
                    dt = _parse_exif_date(str(value))
                    if dt:
                        return dt
        except Exception:
            pass

        # Legacy _getexif() API
        try:
            legacy = getattr(img, "_getexif", None)
            if legacy:
                exif_data = legacy()
                if exif_data:
                    for tag_id in _EXIF_DATE_TAGS:
                        value = exif_data.get(tag_id)
                        if value:
                            dt = _parse_exif_date(str(value))
                            if dt:
                                return dt
        except Exception:
            pass

    except Exception:
        pass

    # Filename patterns (common phone naming conventions)
    dt = _date_from_filename(image_path)
    if dt:
        return dt

    # Last resort: file mtime
    return datetime.fromtimestamp(os.path.getmtime(image_path))


# ── Font helpers ───────────────────────────────────────────────────────────────

def load_font(font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[str] = []

    if font_path:
        candidates.append(font_path)

    candidates.extend([
        str(Path("fonts") / "Nunito-SemiBold.ttf"),
        str(Path("fonts") / "Roboto-Regular.ttf"),
        str(Path("fonts") / "Arial.ttf"),
    ])

    if sys.platform == "darwin":
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        ])
    elif sys.platform.startswith("win"):
        candidates.extend([
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
        ])
    else:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ])

    for p in candidates:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, font_size)
        except:
            pass

    return ImageFont.load_default()


def text_bbox_with_spacing(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    letter_spacing: int,
) -> Tuple[int, int, int, int]:
    x: float = 0.0
    h: float = 0.0
    ls: float = float(letter_spacing)

    for ch in text:
        bbox = draw.textbbox((0, 0), ch, font=font)
        ch_w: float = float(bbox[2] - bbox[0])
        ch_h: float = float(bbox[3] - bbox[1])
        h = max(h, ch_h)
        x += ch_w + ls

    if text:
        x -= ls

    return (0, 0, int(round(x)), int(round(h)))


def draw_text_with_spacing(
    draw: ImageDraw.ImageDraw,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: Tuple[int, int, int],
    letter_spacing: int,
    stroke_width: int = 0,
    stroke_fill: Optional[Tuple[int, int, int]] = None,
) -> None:
    x: float = float(pos[0])
    y: int = pos[1]
    ls: float = float(letter_spacing)

    for ch in text:
        draw.text(
            (int(round(x)), y),
            ch,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        bbox = draw.textbbox((0, 0), ch, font=font)
        ch_w: float = float(bbox[2] - bbox[0])
        x += ch_w + ls


# ── Watermark ──────────────────────────────────────────────────────────────────

def calculate_font_size(img_width: int, img_height: int, base_font_size: int) -> int:
    is_vertical = img_height > img_width

    if is_vertical:
        reference_width = 3000
        scale_factor = img_width / reference_width
        adjusted_size = int(base_font_size * scale_factor * 0.8)
    else:
        reference_width = 4000
        scale_factor = img_width / reference_width
        adjusted_size = int(base_font_size * scale_factor)

    return max(30, min(adjusted_size, 100))


def calculate_text_position(
    img_size: Tuple[int, int],
    text_bbox: Tuple[int, int, int, int],
    position: str,
    margin: int,
) -> Tuple[int, int]:
    img_w, img_h = img_size
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    if position == "bottom_left":
        return (margin, img_h - text_h - margin)
    if position == "bottom_right":
        return (img_w - text_w - margin, img_h - text_h - margin)
    if position == "top_left":
        return (margin, margin)
    if position == "top_right":
        return (img_w - text_w - margin, margin)

    return (margin, img_h - text_h - margin)


def add_watermark(image_path: str, output_path: str, config: Config) -> None:
    img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")

    dynamic_font_size = calculate_font_size(img.width, img.height, config.font_size)

    photo_date = get_photo_date(image_path)
    date_text = photo_date.strftime(config.date_format)

    draw = ImageDraw.Draw(img)
    font = load_font(config.font_path, dynamic_font_size)

    bbox = text_bbox_with_spacing(draw, date_text, font, config.letter_spacing)
    pos = calculate_text_position(img.size, bbox, config.position, config.margin)

    if config.use_shadow:
        shadow_pos = (pos[0] + config.shadow_offset[0], pos[1] + config.shadow_offset[1])
        draw_text_with_spacing(
            draw, shadow_pos, date_text, font, config.shadow_color,
            config.letter_spacing, stroke_width=0, stroke_fill=None,
        )

    draw_text_with_spacing(
        draw, pos, date_text, font, config.text_color,
        config.letter_spacing, stroke_width=config.stroke_width, stroke_fill=config.stroke_fill,
    )

    img.save(output_path, quality=config.quality)


# ── Grouping ───────────────────────────────────────────────────────────────────

def group_photos_by_time(photos: List[Path], config: Config) -> List[List[Path]]:
    if not photos:
        return []

    max_gap_seconds = config.max_gap_minutes * 60

    dated = sorted(
        ((get_photo_date(str(p)), p) for p in photos),
        key=lambda x: x[0],
    )

    groups: List[List[Path]] = [[dated[0][1]]]
    for i in range(1, len(dated)):
        gap = (dated[i][0] - dated[i - 1][0]).total_seconds()
        if gap > max_gap_seconds:
            prev_dt = dated[i - 1][0].strftime("%H:%M")
            curr_dt = dated[i][0].strftime("%H:%M")
            print(f"  Split: {prev_dt} → {curr_dt} ({gap / 60:.1f} min gap)")
            groups.append([])
        groups[-1].append(dated[i][1])

    return groups


def folder_name_for_group(photos: List[Path]) -> str:
    dt = get_photo_date(str(photos[0]))
    return dt.strftime("%Hh%M_%d-%m-%Y")


# ── Batch processing ───────────────────────────────────────────────────────────

def collect_photos(directory: Path) -> List[Path]:
    seen: set[Path] = set()
    for p in PHOTO_PATTERNS:
        for photo in directory.glob(p):
            seen.add(photo.resolve())
    return list(seen)


def _out_name(photo: Path) -> str:
    return photo.stem + ".jpg" if photo.suffix.lower() == ".heic" else photo.name


def _watermark_batch(photos: List[Path], output_dir: Path, config: Config) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    print(f"Found: {len(photos)} photos  →  {output_dir}\n")
    ok = 0
    failed = 0
    for i, photo in enumerate(photos, 1):
        out_path = output_dir / _out_name(photo)
        try:
            add_watermark(str(photo), str(out_path), config)
            ok += 1
            print(f"  [{i}/{len(photos)}] {photo.name} [OK]")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(photos)}] {photo.name} [ERROR]: {e}")
    print(f"  Done: {ok}/{len(photos)}  Fail: {failed}\n")


def _group_batch(photos: List[Path], output_dir: Path, config: Config) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    print(f"Found: {len(photos)} photos  →  {output_dir}")
    groups = group_photos_by_time(photos, config)
    print(f"Detected groups: {len(groups)}\n")

    ok = 0
    failed = 0
    total = sum(len(g) for g in groups)

    for i, group in enumerate(groups, 1):
        folder_name = folder_name_for_group(group)
        group_dir = output_dir / folder_name
        group_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Group {i}/{len(groups)}: {folder_name} ({len(group)} photos)")

        for photo in group:
            out_path = group_dir / _out_name(photo)
            try:
                if config.mode == "group":
                    shutil.copy2(str(photo), str(out_path))
                else:
                    add_watermark(str(photo), str(out_path), config)
                ok += 1
                print(f"    {photo.name} [OK]")
            except Exception as e:
                failed += 1
                print(f"    {photo.name} [ERROR]: {e}")

    print(f"  Done: {ok}/{total}  Fail: {failed}\n")


# ── Top-level processors ───────────────────────────────────────────────────────

def process_photos(config: Config) -> None:
    input_dir = Path(config.input_folder)
    output_dir = Path(config.output_folder)
    output_dir.mkdir(exist_ok=True)

    direct = collect_photos(input_dir)
    if direct:
        print("[Root input/]")
        _watermark_batch(direct, output_dir, config)

    for subdir in sorted(input_dir.iterdir()):
        if not subdir.is_dir():
            continue
        photos = collect_photos(subdir)
        if not photos:
            continue
        sub_output = output_dir / f"{subdir.name}_Date"
        print(f"[{subdir.name}]")
        _watermark_batch(photos, sub_output, config)

    if not direct and not any(
        collect_photos(s) for s in input_dir.iterdir() if s.is_dir()
    ):
        print(f"[WARNING] No photos found in: {input_dir}")


def process_groups(config: Config) -> None:
    input_dir = Path(config.input_folder)
    output_dir = Path(config.output_folder)
    output_dir.mkdir(exist_ok=True)

    direct = collect_photos(input_dir)
    if direct:
        print("[Root input/]")
        _group_batch(direct, output_dir, config)

    for subdir in sorted(input_dir.iterdir()):
        if not subdir.is_dir():
            continue
        photos = collect_photos(subdir)
        if not photos:
            continue
        sub_output = output_dir / f"{subdir.name}_DateOrder"
        print(f"[{subdir.name}]")
        _group_batch(photos, sub_output, config)

    if not direct and not any(
        collect_photos(s) for s in input_dir.iterdir() if s.is_dir()
    ):
        print(f"[WARNING] No photos found in: {input_dir}")
