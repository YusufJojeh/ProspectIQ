from __future__ import annotations

from pathlib import Path
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "src" / "assets" / "marketing"
SIZE = (1600, 1200)

PALETTE = {
    "night": (9, 24, 31),
    "deep": (14, 42, 47),
    "teal": (33, 199, 188),
    "mint": (138, 249, 221),
    "cream": (239, 247, 241),
    "amber": (249, 168, 37),
    "sand": (255, 234, 182),
    "slate": (99, 118, 129),
}


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[index] * (1 - t) + b[index] * t) for index in range(3))


def gradient_background(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size)
    pixels = image.load()
    for y in range(height):
        row_color = mix(top, bottom, y / max(height - 1, 1))
        for x in range(width):
            tilt = 0.08 * math.sin((x / width) * math.pi)
            pixels[x, y] = (*mix(row_color, PALETTE["deep"], tilt), 255)
    return image


def add_noise(base: Image.Image, intensity: int = 14, alpha: int = 24) -> None:
    random.seed(42)
    noise = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(noise)
    for _ in range(6500):
        x = random.randint(0, base.width - 1)
        y = random.randint(0, base.height - 1)
        shade = random.randint(0, intensity)
        draw.point((x, y), fill=(255 - shade, 255 - shade, 255 - shade, alpha))
    base.alpha_composite(noise)


def add_glow(base: Image.Image, center: tuple[int, int], radius: int, color: tuple[int, int, int], alpha: int) -> None:
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=radius // 2))
    base.alpha_composite(glow)


def draw_grid(base: Image.Image, horizon: int, spacing: int, color: tuple[int, int, int, int]) -> None:
    grid = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(grid)
    width, height = base.size

    for y in range(horizon, height + spacing, spacing):
        perspective = (y - horizon) / max(height - horizon, 1)
        left = int(width * 0.17 * (1 - perspective))
        right = int(width - width * 0.17 * (1 - perspective))
        draw.line((left, y, right, y), fill=color, width=1)

    vanishing_x = width // 2
    for offset in range(-9, 10):
        start_x = vanishing_x + offset * 90
        draw.line((start_x, height, vanishing_x, horizon), fill=color, width=1)

    grid = grid.filter(ImageFilter.GaussianBlur(radius=0.5))
    base.alpha_composite(grid)


def draw_panel_shadow(layer: Image.Image, points: list[tuple[float, float]], blur: int = 18) -> None:
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    shadow_points = [(x + 18, y + 30) for x, y in points]
    draw.polygon(shadow_points, fill=(4, 10, 13, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
    layer.alpha_composite(shadow)


def draw_isometric_panel(
    base: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
    depth: int,
    face: tuple[int, int, int, int],
    top: tuple[int, int, int, int],
    side: tuple[int, int, int, int],
    line: tuple[int, int, int, int],
) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    front = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    top_face = [(x, y), (x + depth, y - depth), (x + width + depth, y - depth), (x + width, y)]
    side_face = [
        (x + width, y),
        (x + width + depth, y - depth),
        (x + width + depth, y + height - depth),
        (x + width, y + height),
    ]
    draw_panel_shadow(layer, front)
    draw.polygon(side_face, fill=side)
    draw.polygon(top_face, fill=top)
    draw.polygon(front, fill=face)
    draw.line(front + [front[0]], fill=line, width=3)
    draw.line(top_face + [top_face[0]], fill=line, width=2)
    draw.line(side_face + [side_face[0]], fill=line, width=2)

    content = Image.new("RGBA", base.size, (0, 0, 0, 0))
    content_draw = ImageDraw.Draw(content)
    inset_x = x + 34
    inset_y = y + 44
    for index, width_scale in enumerate((0.58, 0.78, 0.84, 0.66)):
        bar_width = int(width * width_scale)
        bar_height = 18 if index == 0 else 12
        bar_color = (238, 250, 245, 230 if index == 0 else 120)
        content_draw.rounded_rectangle(
            (inset_x, inset_y + index * 38, inset_x + bar_width, inset_y + index * 38 + bar_height),
            radius=8,
            fill=bar_color,
        )
    for column, scale in enumerate((0.36, 0.52, 0.7)):
        chart_width = 48
        chart_height = int(height * scale)
        left = x + 42 + column * 76
        top_bar = y + height - chart_height - 42
        content_draw.rounded_rectangle(
            (left, top_bar, left + chart_width, y + height - 32),
            radius=16,
            fill=(*PALETTE["teal"], 170 + column * 12),
        )
    ring_center = (x + width - 120, y + 118)
    content_draw.ellipse(
        (ring_center[0] - 48, ring_center[1] - 48, ring_center[0] + 48, ring_center[1] + 48),
        outline=(*PALETTE["mint"], 160),
        width=6,
    )
    content_draw.ellipse(
        (ring_center[0] - 20, ring_center[1] - 20, ring_center[0] + 20, ring_center[1] + 20),
        fill=(*PALETTE["amber"], 205),
    )

    base.alpha_composite(layer)
    base.alpha_composite(content)


def draw_glass_card(
    base: Image.Image,
    box: tuple[int, int, int, int],
    accent: tuple[int, int, int],
    highlight: tuple[int, int, int],
) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0 + 14, y0 + 20, x1 + 14, y1 + 20), radius=32, fill=(5, 14, 18, 100))
    draw.rounded_rectangle(box, radius=32, fill=(255, 255, 255, 38), outline=(255, 255, 255, 90), width=2)
    draw.rounded_rectangle((x0 + 20, y0 + 24, x1 - 20, y0 + 60), radius=18, fill=(*highlight, 150))
    for index in range(3):
        top = y0 + 100 + index * 54
        draw.rounded_rectangle(
            (x0 + 24, top, x1 - 24, top + 18),
            radius=10,
            fill=(255, 255, 255, 55 if index else 90),
        )
    draw.ellipse((x1 - 112, y1 - 112, x1 - 36, y1 - 36), fill=(*accent, 215))
    draw.ellipse((x1 - 152, y1 - 152, x1, y1), outline=(*highlight, 120), width=3)
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=0.3)))


def draw_pin_cluster(base: Image.Image, points: list[tuple[int, int]], color: tuple[int, int, int]) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for x, y in points:
        draw.line((x, y + 16, x, y + 60), fill=(*color, 160), width=3)
        draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(*color, 230))
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(250, 255, 252, 240))
        draw.ellipse((x - 42, y + 54, x + 42, y + 74), fill=(*color, 40))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=1)))


def build_hero_scene() -> Image.Image:
    base = gradient_background(SIZE, PALETTE["night"], (13, 52, 56))
    add_glow(base, (1220, 170), 210, PALETTE["teal"], 110)
    add_glow(base, (290, 920), 240, PALETTE["amber"], 85)
    add_glow(base, (1180, 880), 320, PALETTE["mint"], 34)
    draw_grid(base, horizon=670, spacing=66, color=(113, 170, 164, 54))
    draw_isometric_panel(
        base,
        x=390,
        y=300,
        width=560,
        height=390,
        depth=68,
        face=(246, 252, 248, 220),
        top=(176, 242, 229, 175),
        side=(22, 116, 109, 195),
        line=(255, 255, 255, 120),
    )
    draw_isometric_panel(
        base,
        x=1040,
        y=250,
        width=250,
        height=180,
        depth=28,
        face=(255, 255, 255, 175),
        top=(249, 168, 37, 120),
        side=(19, 85, 79, 170),
        line=(255, 255, 255, 110),
    )
    draw_isometric_panel(
        base,
        x=170,
        y=420,
        width=230,
        height=170,
        depth=24,
        face=(255, 255, 255, 165),
        top=(138, 249, 221, 110),
        side=(13, 88, 86, 160),
        line=(255, 255, 255, 95),
    )
    draw_pin_cluster(base, [(250, 756), (330, 728), (410, 784), (510, 738)], PALETTE["amber"])
    draw_pin_cluster(base, [(1160, 790), (1260, 740), (1340, 812)], PALETTE["teal"])
    add_noise(base)
    return base


def build_evidence_scene() -> Image.Image:
    base = gradient_background(SIZE, (13, 30, 34), (21, 55, 60))
    add_glow(base, (1180, 260), 260, PALETTE["teal"], 120)
    add_glow(base, (420, 920), 260, PALETTE["amber"], 100)
    add_glow(base, (1080, 780), 320, PALETTE["mint"], 44)
    draw_grid(base, horizon=760, spacing=72, color=(110, 172, 163, 36))
    draw_glass_card(base, (200, 230, 760, 850), PALETTE["amber"], PALETTE["sand"])
    draw_glass_card(base, (490, 180, 1050, 800), PALETTE["teal"], PALETTE["mint"])
    draw_glass_card(base, (820, 260, 1380, 880), PALETTE["amber"], PALETTE["sand"])
    ring = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ring)
    for radius, alpha in ((180, 115), (255, 75), (340, 32)):
        draw.ellipse((760 - radius, 530 - radius, 760 + radius, 530 + radius), outline=(*PALETTE["mint"], alpha), width=4)
    base.alpha_composite(ring.filter(ImageFilter.GaussianBlur(radius=1)))
    add_noise(base)
    return base


def build_workflow_scene() -> Image.Image:
    base = gradient_background(SIZE, (10, 22, 28), (17, 44, 49))
    add_glow(base, (320, 260), 180, PALETTE["amber"], 120)
    add_glow(base, (1220, 220), 210, PALETTE["teal"], 110)
    add_glow(base, (820, 860), 360, PALETTE["mint"], 50)
    draw_grid(base, horizon=700, spacing=70, color=(105, 164, 160, 42))

    points = [(220, 660), (500, 520), (820, 590), (1120, 470), (1360, 560)]
    flow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(flow)
    for index in range(len(points) - 1):
        draw.line((*points[index], *points[index + 1]), fill=(*PALETTE["mint"], 110), width=10)
    flow = flow.filter(ImageFilter.GaussianBlur(radius=2))
    base.alpha_composite(flow)

    for index, (x, y) in enumerate(points):
        width = 190 if index % 2 == 0 else 220
        draw_isometric_panel(
            base,
            x=x - 70,
            y=y - 160,
            width=width,
            height=120,
            depth=20,
            face=(255, 255, 255, 170),
            top=((*PALETTE["teal"], 110) if index % 2 else (*PALETTE["amber"], 110)),
            side=(17, 86, 81, 170),
            line=(255, 255, 255, 95),
        )
    draw_pin_cluster(base, [(260, 850), (760, 820), (1240, 830)], PALETTE["amber"])
    add_noise(base)
    return base


def save_png(image: Image.Image, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUTPUT_DIR / filename, format="PNG", optimize=True)


def main() -> None:
    save_png(build_hero_scene(), "leadscope-hero-scene.png")
    save_png(build_evidence_scene(), "leadscope-evidence-scene.png")
    save_png(build_workflow_scene(), "leadscope-workflow-scene.png")


if __name__ == "__main__":
    main()

