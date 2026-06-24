"""
Renders carousel outline text into actual PNG images Instagram can post.

This exists because Claude's drafts produce a *script* for the carousel
(text lines), not pixels - and Instagram's API needs real image files at
public URLs. This module closes that gap with a simple branded template.
Swap the colors/fonts below to match your actual brand if you want
something fancier than this starting template.
"""

import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")
FONT_BOLD = os.path.join(ASSETS_DIR, "Poppins-Bold.ttf")
FONT_REGULAR = os.path.join(ASSETS_DIR, "Poppins-Regular.ttf")

CANVAS_SIZE = (1080, 1080)
BG_COLOR = (20, 20, 24)
TEXT_COLOR = (245, 245, 245)
ACCENT_COLOR = (130, 170, 255)
MARGIN = 100


def _wrapped_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    avg_char_width = font.getlength("x") or 20
    wrap_chars = max(10, int(max_width / avg_char_width))
    return textwrap.wrap(text, width=wrap_chars)


def render_slide(text: str, slide_number: int, total_slides: int, out_path: str) -> str:
    """Render a single carousel slide and save it as a PNG. Returns out_path."""
    img = Image.new("RGB", CANVAS_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)

    body_font = ImageFont.truetype(FONT_BOLD, 64 if slide_number == 1 else 56)
    small_font = ImageFont.truetype(FONT_REGULAR, 32)

    max_text_width = CANVAS_SIZE[0] - 2 * MARGIN
    lines = _wrapped_lines(draw, text, body_font, max_text_width)

    line_height = int(body_font.size * 1.3)
    total_text_height = line_height * len(lines)
    start_y = (CANVAS_SIZE[1] - total_text_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=body_font)
        line_width = bbox[2] - bbox[0]
        x = (CANVAS_SIZE[0] - line_width) // 2
        y = start_y + i * line_height
        draw.text((x, y), line, font=body_font, fill=TEXT_COLOR)

    # slide indicator dots at the bottom
    dot_radius = 6
    dot_gap = 22
    total_dots_width = (total_slides - 1) * dot_gap
    start_x = (CANVAS_SIZE[0] - total_dots_width) // 2
    dot_y = CANVAS_SIZE[1] - 70
    for i in range(total_slides):
        cx = start_x + i * dot_gap
        color = ACCENT_COLOR if i == slide_number - 1 else (90, 90, 96)
        draw.ellipse([cx - dot_radius, dot_y - dot_radius, cx + dot_radius, dot_y + dot_radius], fill=color)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def render_carousel(hook: str, carousel_lines: list[str], slug: str, output_dir: str) -> list[str]:
    """
    Renders the hook as slide 1 and each carousel line as a following slide.
    Returns a list of file paths to the rendered PNGs, in order.
    """
    all_slides_text = [hook] + list(carousel_lines)
    total = len(all_slides_text)
    paths = []
    for i, text in enumerate(all_slides_text, start=1):
        out_path = os.path.join(output_dir, slug, f"slide-{i}.png")
        render_slide(text, i, total, out_path)
        paths.append(out_path)
    return paths
