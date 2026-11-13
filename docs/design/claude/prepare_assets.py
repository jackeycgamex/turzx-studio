"""Export the generated wallpapers at native display sizes without palette PNGs."""

import argparse
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[3]
DESTINATION = ROOT / "web" / "assets" / "claude"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v1", "v2", "v3", "v3-thought", "v3-greeting"), default="v3")
    args = parser.parse_args()
    prefix = f"claude-{args.version}" if args.version != "v1" else "claude"
    DESTINATION.mkdir(parents=True, exist_ok=True)
    quantize_channel = [min(255, ((value + 4) // 8) * 8) for value in range(256)]
    for orientation, size in (("landscape", (1280, 720)), ("portrait", (720, 1280))):
        source_orientation = "landscape" if args.version.startswith("v3") else orientation
        source = Path(__file__).with_name(f"{prefix}-{source_orientation}-original.png")
        with Image.open(source) as original:
            if args.version.startswith("v3") and orientation == "portrait":
                picture = ImageOps.fit(original.convert("RGB"), size, Image.Resampling.LANCZOS,
                                       centering=(1, .5))
            else:
                picture = original.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        if not args.version.startswith("v3"):
            picture = picture.point(quantize_channel * 3)
        picture = picture.convert("RGBA")
        destination = DESTINATION / f"{prefix}-{orientation}.png"
        picture.save(destination, compress_level=9)
        with Image.open(destination) as saved:
            assert saved.size == size
            assert saved.mode == "RGBA"
            assert saved.getchannel("A").getextrema() == (255, 255)
        print(f"{destination}: {destination.stat().st_size} bytes, RGBA {size[0]}x{size[1]}")


if __name__ == "__main__":
    main()
