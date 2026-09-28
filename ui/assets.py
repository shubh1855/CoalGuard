from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "images"
DEFAULT_IMAGE = ASSETS_DIR / "test_results.png"
LOGO_IMAGE = ASSETS_DIR / "logo.svg"
PAGE_ICON_IMAGE = ASSETS_DIR / "page_icon.png"


def load_page_icon() -> Image.Image | str:
    if not PAGE_ICON_IMAGE.exists():
        return "🛡️"

    icon = Image.open(PAGE_ICON_IMAGE).convert("RGBA")
    contained = ImageOps.contain(icon, (192, 192), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (256, 256), (11, 18, 32, 255))
    offset = (
        (canvas.width - contained.width) // 2,
        (canvas.height - contained.height) // 2,
    )
    canvas.paste(contained, offset, contained)
    return canvas


def load_default_image() -> Image.Image:
    if DEFAULT_IMAGE.exists():
        return Image.open(DEFAULT_IMAGE)
    return Image.new("RGB", (1280, 720), color=(245, 247, 250))


def load_logo() -> str | None:
    return str(LOGO_IMAGE) if LOGO_IMAGE.exists() else None
