from __future__ import annotations

import pillow_heif # type: ignore[import-untyped]

pillow_heif.register_heif_opener()

from config import CONFIG
from functions import process_photos, process_groups


def main() -> None:
    print("=" * 50)
    print("Automatic Watermarking and Order System")
    print("=" * 50)
    print()

    if CONFIG.mode in ("group", "both"):
        process_groups(CONFIG)
    else:
        process_photos(CONFIG)


if __name__ == "__main__":
    main()
