"""M0 Foundation: crop screenshot evidence files in place."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def parse_crop(value: str) -> tuple[str, tuple[int, int, int, int]]:
    try:
        filename, box_text = value.split("=", 1)
        box = tuple(int(part.strip()) for part in box_text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Crop must use file.png=left,top,right,bottom"
        ) from exc

    if len(box) != 4:
        raise argparse.ArgumentTypeError("Crop box must contain four integers")

    left, top, right, bottom = box
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("Crop box must have right > left and bottom > top")

    return filename, box


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Directory containing screenshot files")
    parser.add_argument(
        "--crop",
        action="append",
        required=True,
        type=parse_crop,
        help="Crop spec: file.png=left,top,right,bottom. Repeat for multiple files.",
    )
    args = parser.parse_args()

    base = Path(args.base)
    if not base.is_dir():
        raise SystemExit(f"Base directory not found: {base}")

    for filename, box in args.crop:
        path = base / filename
        if not path.is_file():
            raise SystemExit(f"Screenshot not found: {path}")

        image = Image.open(path)
        image.crop(box).save(path)
        print(f"cropped {path} to {box}")


if __name__ == "__main__":
    main()
