from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Config:
    input_folder: str = "input"
    output_folder: str = "output"
    # Watermark
    font_size: int = 75
    font_path: Optional[str] = None
    letter_spacing: int = 2
    text_color: Tuple[int, int, int] = (255, 255, 255)
    shadow_color: Tuple[int, int, int] = (0, 0, 0)
    shadow_offset: Tuple[int, int] = (2, 2)
    stroke_width: int = 1
    stroke_fill: Tuple[int, int, int] = (255, 255, 255)
    position: str = "bottom_left"
    margin: int = 30
    date_format: str = "%d %B %Y %H:%M"
    quality: int = 95
    use_shadow: bool = False
    # Mode: "watermark", "group", "both"
    mode: str = "group"
    # Split into a new group when the gap between consecutive photos exceeds this value
    max_gap_minutes: float = 10.0


CONFIG = Config()

PHOTO_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.heic", "*.JPG", "*.JPEG", "*.PNG", "*.HEIC")
