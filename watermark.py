from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS


@dataclass(frozen=True)
class Config:
    #Configuration of the water mark

    input_folder: str = "input"
    output_folder: str = "output"
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


CONFIG = Config()


def calculate_font_size(img_width: int, img_height: int, base_font_size: int) -> int:
    """
    Calcula el tamaño de fuente apropiado según la orientación y tamaño de la imagen
    """
    # Determinar si es vertical u horizontal
    is_vertical = img_height > img_width
    
    if is_vertical:
        # Para fotos verticales, usar el ancho como referencia
        # Escalar basado en un ancho base de 3000px
        reference_width = 3000
        scale_factor = img_width / reference_width
        adjusted_size = int(base_font_size * scale_factor * 0.8)  # 80% del tamaño para verticales
    else:
        # Para fotos horizontales, usar el ancho como referencia
        reference_width = 4000
        scale_factor = img_width / reference_width
        adjusted_size = int(base_font_size * scale_factor)
    
    # Asegurar un tamaño mínimo y máximo razonable
    return max(30, min(adjusted_size, 100))


def get_photo_date(image_path: str) -> datetime:
    """
    Extract photo creation time
    """
    try:
        img = Image.open(image_path)
        exif = getattr(img, "_getexif", None)
        if exif:
            exif_data = exif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ("DateTimeOriginal", "DateTime"):
                        try:
                            return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                        except:
                            pass
    except:
        pass

    #Use Last Modification in case of not found the other
    ts = os.path.getmtime(image_path)
    return datetime.fromtimestamp(ts)


def load_font(font_path: Optional[str], font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Carga fuente con fallbacks para diferentes sistemas operativos
    """
    candidates: list[str] = []
    
    # Agregar fuente especificada por usuario
    if font_path:
        candidates.append(font_path)
    
    # Fuentes en carpeta local
    candidates.extend([
        str(Path("fonts") / "Nunito-SemiBold.ttf"),
        str(Path("fonts") / "Roboto-Regular.ttf"),
        str(Path("fonts") / "Arial.ttf"),
    ])
    
    # Fuentes del sistema segun plataforma
    if sys.platform == "darwin":  # macOS
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        ])
    elif sys.platform.startswith("win"):  # Windows
        candidates.extend([
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
        ])
    else:  # Linux
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ])
    
    # Intentar cargar cada fuente candidata
    for p in candidates:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, font_size)
        except:
            pass
    
    # Ultimo recurso: fuente por defecto
    return ImageFont.load_default()


def text_bbox_with_spacing(
    draw: ImageDraw.ImageDraw, 
    text: str, 
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont, 
    letter_spacing: int
) -> Tuple[int, int, int, int]:
    """
    Calcula el bounding box del texto con espaciado entre letras
    """
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
    """
    Dibuja texto con espaciado personalizado entre letras
    """
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


def calculate_text_position(
    img_size: Tuple[int, int],
    text_bbox: Tuple[int, int, int, int],
    position: str,
    margin: int,
) -> Tuple[int, int]:
    """
    Calcula la posicion del texto en la imagen
    """
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

    # Default: bottom_left
    return (margin, img_h - text_h - margin)


def add_watermark(image_path: str, output_path: str, config: Config) -> None:
    """
    Agrega watermark de fecha a una foto
    """
    # Abrir y convertir imagen
    img = Image.open(image_path).convert("RGB")
    
    # Calcular tamaño de fuente apropiado según dimensiones de la imagen
    dynamic_font_size = calculate_font_size(img.width, img.height, config.font_size)
    
    # Obtener fecha de la foto
    photo_date = get_photo_date(image_path)
    date_text = photo_date.strftime(config.date_format)

    # Preparar para dibujar
    draw = ImageDraw.Draw(img)
    font = load_font(config.font_path, dynamic_font_size)

    # Calcular posicion del texto con espaciado
    bbox = text_bbox_with_spacing(draw, date_text, font, config.letter_spacing)
    pos = calculate_text_position(img.size, bbox, config.position, config.margin)

    # Dibujar sombra si esta habilitada
    if config.use_shadow:
        shadow_pos = (pos[0] + config.shadow_offset[0], pos[1] + config.shadow_offset[1])
        draw_text_with_spacing(
            draw,
            shadow_pos,
            date_text,
            font,
            config.shadow_color,
            config.letter_spacing,
            stroke_width=0,
            stroke_fill=None,
        )

    # Dibujar texto principal
    draw_text_with_spacing(
        draw,
        pos,
        date_text,
        font,
        config.text_color,
        config.letter_spacing,
        stroke_width=config.stroke_width,
        stroke_fill=config.stroke_fill,
    )

    # Guardar imagen
    img.save(output_path, quality=config.quality)


def process_photos(config: Config) -> None:
    input_dir = Path(config.input_folder)
    output_dir = Path(config.output_folder)

    output_dir.mkdir(exist_ok=True)

    patterns = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG")
    photos: list[Path] = []
    for p in patterns:
        photos.extend(input_dir.glob(p))

    if not photos:
        print(f"[WARNING] No photos found in: {input_dir}")
        return

    print(f"Found: {len(photos)} Photos")
    print(f"Save in: {output_dir}\n")

    ok = 0
    failed = 0
    
    for i, photo in enumerate(photos, 1):
        out_path = output_dir / photo.name
        try:
            add_watermark(str(photo), str(out_path), config)
            ok += 1
            print(f"[{i}/{len(photos)}] {photo.name} [OK]")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(photos)}] {photo.name} [ERROR]: {e}")

    
    print(f"\n{'='*50}")
    print(f"Process finished")
    print(f"  Done: {ok}/{len(photos)}")
    print(f"  Fail: {failed}")
    print(f"{'='*50}")


def main() -> None:
    """
    Punto de entrada principal
    """
    print("="*50)
    print("Sistema de Watermarking Automatico")
    print("="*50)
    print()
    
    process_photos(CONFIG)


if __name__ == "__main__":
    main()