"""Generates crisp, professional stock chart icons and multi-resolution ICO files for EGX Terminal."""

import os
from pathlib import Path
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = PROJECT_ROOT / "frontend" / "public"
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


def draw_egx_icon(size: int = 512) -> Image.Image:
    """Draws a modern high-resolution 1:1 stock chart icon using Pillow."""
    # Create RGBA image with high supersampling if needed
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = size / 512.0

    def s(val):
        return int(val * scale)

    # 1. Dark Rounded Container
    margin = s(16)
    radius = s(96)
    # Background gradient approximation (dark slate-navy)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=(11, 16, 27, 255),
        outline=(30, 41, 59, 255),
        width=max(1, s(6))
    )

    # 2. Subtle grid lines
    grid_color = (30, 41, 59, 180)
    for y_pos in [160, 260, 360]:
        y = s(y_pos)
        draw.line([(s(70), y), (s(442), y)], fill=grid_color, width=max(1, s(2)))

    # 3. Candlestick 1 (Left - Green)
    c1_x = s(140)
    c1_w = s(24)
    draw.line([(c1_x, s(210)), (c1_x, s(380))], fill=(5, 150, 105, 255), width=max(2, s(6)))
    draw.rounded_rectangle(
        [c1_x - c1_w, s(255), c1_x + c1_w, s(340)],
        radius=s(8),
        fill=(16, 185, 129, 255),
        outline=(5, 150, 105, 255),
        width=max(1, s(3))
    )

    # 4. Candlestick 2 (Middle - Cyan/Blue)
    c2_x = s(246)
    c2_w = s(24)
    draw.line([(c2_x, s(180)), (c2_x, s(365))], fill=(2, 132, 199, 255), width=max(2, s(6)))
    draw.rounded_rectangle(
        [c2_x - c2_w, s(220), c2_x + c2_w, s(315)],
        radius=s(8),
        fill=(14, 165, 233, 255),
        outline=(2, 132, 199, 255),
        width=max(1, s(3))
    )

    # 5. Candlestick 3 (Right - Bullish Emerald)
    c3_x = s(352)
    c3_w = s(24)
    draw.line([(c3_x, s(110)), (c3_x, s(330))], fill=(16, 185, 129, 255), width=max(2, s(6)))
    draw.rounded_rectangle(
        [c3_x - c3_w, s(140), c3_x + c3_w, s(270)],
        radius=s(8),
        fill=(52, 211, 153, 255),
        outline=(16, 185, 129, 255),
        width=max(1, s(3))
    )

    # 6. Smooth Upward Dynamic Trend Line
    points = [
        (s(90), s(350)),
        (s(140), s(320)),
        (s(200), s(270)),
        (s(246), s(240)),
        (s(300), s(190)),
        (s(352), s(145)),
        (s(410), s(95)),
    ]
    # Draw thicker line with glow effect
    for width_offset, alpha in [(12, 60), (8, 120), (5, 255)]:
        draw.line(points, fill=(52, 211, 153, alpha), width=max(2, s(width_offset)), joint="curve")

    # 7. Glow Dot at the Apex
    dot_x, dot_y = s(410), s(95)
    r_outer = s(16)
    r_inner = s(7)
    draw.ellipse([dot_x - r_outer, dot_y - r_outer, dot_x + r_outer, dot_y + r_outer], fill=(52, 211, 153, 200))
    draw.ellipse([dot_x - r_inner, dot_y - r_inner, dot_x + r_inner, dot_y + r_inner], fill=(255, 255, 255, 255))

    return img


def generate_all_icons():
    """Generates all icon files: SVG, PNGs, and Windows multi-resolution ICO."""
    print("Generating 512x512 master icon...")
    master_icon = draw_egx_icon(512)

    # 1. Save PNG versions for Web, PWA, and Mobile
    png_targets = {
        PUBLIC_DIR / "icon-512.png": 512,
        PUBLIC_DIR / "icon-192.png": 192,
        PUBLIC_DIR / "apple-touch-icon.png": 180,
        PUBLIC_DIR / "favicon-32x32.png": 32,
        PUBLIC_DIR / "favicon-16x16.png": 16,
    }

    for path, size in png_targets.items():
        resized = master_icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(path, format="PNG")
        print(f"Saved: {path.name} ({size}x{size})")

    # 2. Save Windows multi-resolution ICO for PyInstaller & browser favicon
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [master_icon.resize(s, Image.Resampling.LANCZOS) for s in ico_sizes]

    # Save to frontend/public/favicon.ico
    favicon_ico = PUBLIC_DIR / "favicon.ico"
    ico_images[0].save(
        favicon_ico,
        format="ICO",
        sizes=ico_sizes,
        append_images=ico_images[1:]
    )
    print(f"Saved: {favicon_ico.name} (Multi-res ICO)")

    # Save to root app.ico for PyInstaller
    root_ico = PROJECT_ROOT / "app.ico"
    ico_images[0].save(
        root_ico,
        format="ICO",
        sizes=ico_sizes,
        append_images=ico_images[1:]
    )
    print(f"Saved: {root_ico.name} for PyInstaller")

    # 3. Create SVG version for ultra crisp browser tabs
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b101b"/>
      <stop offset="100%" stop-color="#040711"/>
    </linearGradient>
    <linearGradient id="lineGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="50%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#34d399"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="96" fill="url(#bg)" stroke="#1e293b" stroke-width="6"/>
  <line x1="70" y1="160" x2="442" y2="160" stroke="#1e293b" stroke-width="2" stroke-dasharray="6,6"/>
  <line x1="70" y1="260" x2="442" y2="260" stroke="#1e293b" stroke-width="2" stroke-dasharray="6,6"/>
  <line x1="70" y1="360" x2="442" y2="360" stroke="#1e293b" stroke-width="2" stroke-dasharray="6,6"/>
  <line x1="140" y1="210" x2="140" y2="380" stroke="#059669" stroke-width="6" stroke-linecap="round"/>
  <rect x="116" y="255" width="48" height="85" rx="8" fill="#10b981"/>
  <line x1="246" y1="180" x2="246" y2="365" stroke="#0284c7" stroke-width="6" stroke-linecap="round"/>
  <rect x="222" y="220" width="48" height="95" rx="8" fill="#0ea5e9"/>
  <line x1="352" y1="110" x2="352" y2="330" stroke="#10b981" stroke-width="6" stroke-linecap="round"/>
  <rect x="328" y="140" width="48" height="130" rx="8" fill="#34d399"/>
  <path d="M 90 350 Q 200 280 246 240 T 410 95" fill="none" stroke="url(#lineGrad)" stroke-width="12" stroke-linecap="round" filter="url(#glow)"/>
  <circle cx="410" cy="95" r="14" fill="#34d399" filter="url(#glow)"/>
  <circle cx="410" cy="95" r="6" fill="#ffffff"/>
</svg>"""
    svg_path = PUBLIC_DIR / "favicon.svg"
    svg_path.write_text(svg_content, encoding="utf-8")
    print(f"Saved: {svg_path.name} (Vector SVG)")


if __name__ == "__main__":
    generate_all_icons()
