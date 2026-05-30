"""
Deterministic 2D building elevation renderer.

Every call with the same (building_type, style, floors, size) produces
a pixel-identical PNG — guaranteed by zero use of random() anywhere here.

Background is ALWAYS #E0E0E0. This is locked so 3D pipelines always
see the same baseline and can reliably edge-detect the building silhouette.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Tuple

from PIL import Image, ImageDraw

# ── Constants locked for 3D pipeline consistency ──────────────────────────────
BG: Tuple[int, int, int] = (224, 224, 224)   # #E0E0E0 — never changes
CANVAS_W = 800
CANVAS_H = 1000
GROUND_Y = 870                                # fixed ground line y-coordinate


# ── Style palettes ─────────────────────────────────────────────────────────────
# Each style maps to a deterministic color set. Same style = identical colors
# regardless of floor count or size.
PALETTES = {
    "modern_glass_tower": {
        "facade_a": (82,  130, 158),
        "facade_b": (108, 166, 196),
        "window":   (190, 222, 242),
        "mullion":  (40,  55,  72),
        "podium":   (48,  62,  80),
        "roof":     (34,  46,  60),
        "shadow":   (190, 190, 190),
    },
    "traditional_brick": {
        "facade_a": (172,  96,  72),
        "facade_b": (196, 118,  88),
        "window":   (200, 218, 238),
        "mullion":  (128,  70,  52),
        "podium":   (138,  80,  58),
        "roof":     ( 96,  58,  44),
        "shadow":   (190, 184, 180),
    },
    "brutalist_concrete": {
        "facade_a": (148, 150, 154),
        "facade_b": (166, 168, 172),
        "window":   (192, 200, 210),
        "mullion":  (108, 110, 114),
        "podium":   (118, 120, 124),
        "roof":     ( 94,  96, 100),
        "shadow":   (186, 186, 186),
    },
    "retail_complex": {
        "facade_a": (198, 218, 234),
        "facade_b": (218, 234, 246),
        "window":   (228, 242, 252),
        "mullion":  ( 78,  98, 118),
        "podium":   ( 58,  78,  98),
        "roof":     ( 48,  66,  86),
        "shadow":   (186, 188, 190),
    },
}

SIZE_MULT = {"small": 0.72, "medium": 1.0, "large": 1.32}


# ── Public API ─────────────────────────────────────────────────────────────────

def render_building(
    building_type: str,
    style: str,
    floors: int,
    size: str,
) -> bytes:
    """
    Returns a PNG as raw bytes.

    Parameters
    ----------
    building_type : "skyscraper" | "house" | "suburban_building"
    style         : "modern_glass_tower" | "traditional_brick"
                    | "brutalist_concrete" | "retail_complex"
    floors        : 1–100
    size          : "small" | "medium" | "large"
    """
    floors = max(1, min(floors, 100))
    p = PALETTES.get(style, PALETTES["modern_glass_tower"])
    sm = SIZE_MULT.get(size, 1.0)

    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(img)

    if building_type == "skyscraper":
        _skyscraper(draw, floors, sm, p)
    elif building_type == "house":
        _house(draw, floors, sm, p)
    else:
        _suburban(draw, floors, sm, p)

    _ground_line(draw)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_building_image(
    building_type: str,
    style: str,
    floors: int,
    size: str,
) -> Image.Image:
    """Same as render_building but returns a PIL Image (useful for compositing)."""
    data = render_building(building_type, style, floors, size)
    return Image.open(BytesIO(data))


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _ground_line(draw: ImageDraw.ImageDraw) -> None:
    draw.line([(0, GROUND_Y), (CANVAS_W, GROUND_Y)], fill=(148, 148, 148), width=2)


def _shadow(draw: ImageDraw.ImageDraw, cx: int, rx: int, p: dict) -> None:
    ry = max(8, rx // 8)
    draw.ellipse(
        [cx - rx, GROUND_Y - ry, cx + rx, GROUND_Y + ry],
        fill=p["shadow"],
    )


# ── Skyscraper ─────────────────────────────────────────────────────────────────
#
# Structure (identical for any floor count — only height changes):
#
#   ┌─────┐   ← penthouse
#  ┌───────┐  ← roof cap
#  │ ┌───┐ │  ← setback floors (top 2, 82% width)
#  │ │   │ │
#  │ │   │ │  ← main tower floors (window strips + mullions)
#  │ │   │ │
# ┌─────────┐ ← podium (4 floors, 122% width, solid color)
# └─────────┘

SKYSCRAPER_FLOOR_H = 14  # px — fixed, never changes
SKYSCRAPER_BASE_W  = 190  # medium tower width in px


def _skyscraper(draw: ImageDraw.ImageDraw, floors: int, sm: float, p: dict) -> None:
    cx = CANVAS_W // 2
    tw = int(SKYSCRAPER_BASE_W * sm)          # tower width
    pw = int(tw * 1.22)                        # podium width

    podium_floors = min(4, floors)
    podium_h      = podium_floors * SKYSCRAPER_FLOOR_H
    tower_h       = floors * SKYSCRAPER_FLOOR_H

    # Clamp so very tall buildings still fit
    if GROUND_Y - tower_h < 60:
        effective_floors = (GROUND_Y - 60) // SKYSCRAPER_FLOOR_H
    else:
        effective_floors = floors

    tower_h  = effective_floors * SKYSCRAPER_FLOOR_H
    podium_h = min(podium_floors, effective_floors) * SKYSCRAPER_FLOOR_H

    t_x1 = cx - tw // 2;  t_x2 = cx + tw // 2
    p_x1 = cx - pw // 2;  p_x2 = cx + pw // 2
    t_y2 = GROUND_Y;       t_y1 = GROUND_Y - tower_h
    p_y1 = GROUND_Y - podium_h

    _shadow(draw, cx, pw // 2, p)

    # Podium
    draw.rectangle([p_x1, p_y1, p_x2, GROUND_Y], fill=p["podium"])

    # Tower floors (above podium)
    setback_start = effective_floors - 2  # top 2 floors are narrower
    sb_w = int(tw * 0.82)
    sb_x1 = cx - sb_w // 2;  sb_x2 = cx + sb_w // 2

    for i in range(podium_floors, effective_floors):
        fy2 = GROUND_Y - i * SKYSCRAPER_FLOOR_H
        fy1 = fy2 - SKYSCRAPER_FLOOR_H

        is_setback = (i >= setback_start and effective_floors > 6)
        x1 = sb_x1 if is_setback else t_x1
        x2 = sb_x2 if is_setback else t_x2

        color = p["facade_a"] if i % 2 == 0 else p["facade_b"]
        draw.rectangle([x1, fy1, x2, fy2], fill=color)

        # Window strip (horizontal band, inset from sides)
        win_y1 = fy1 + int(SKYSCRAPER_FLOOR_H * 0.15)
        win_y2 = fy1 + int(SKYSCRAPER_FLOOR_H * 0.82)
        draw.rectangle([x1 + 5, win_y1, x2 - 5, win_y2], fill=p["window"])

    # Horizontal floor lines on tower face
    for i in range(podium_floors, effective_floors + 1):
        fy = GROUND_Y - i * SKYSCRAPER_FLOOR_H
        x1 = sb_x1 if (i >= setback_start and effective_floors > 6) else t_x1
        x2 = sb_x2 if (i >= setback_start and effective_floors > 6) else t_x2
        draw.line([(x1, fy), (x2, fy)], fill=p["mullion"], width=1)

    # Vertical mullions (fixed spacing relative to tower width)
    mullion_gap = max(28, tw // 6)
    mx = t_x1 + mullion_gap
    while mx < t_x2:
        draw.line([(mx, t_y1), (mx, p_y1)], fill=p["mullion"], width=2)
        mx += mullion_gap

    # Roof cap
    roof_h = max(10, int(tw * 0.07))
    draw.rectangle([t_x1, t_y1 - roof_h, t_x2, t_y1], fill=p["roof"])

    # Penthouse
    pen_w = int(tw * 0.34)
    pen_h = int(roof_h * 1.6)
    draw.rectangle(
        [cx - pen_w // 2, t_y1 - roof_h - pen_h, cx + pen_w // 2, t_y1 - roof_h],
        fill=p["roof"],
    )

    # Podium lobby windows (ground floor)
    _podium_windows(draw, p_x1, p_y1, p_x2, GROUND_Y, p)


def _podium_windows(draw, x1, y1, x2, y2, p):
    """Large lobby / retail windows on podium ground floor."""
    floor_h = y2 - y1
    win_h = int(floor_h * 0.55)
    win_y1 = y1 + int(floor_h * 0.12)
    win_y2 = win_y1 + win_h
    panel_w = (x2 - x1) // 4
    for i in range(4):
        wx1 = x1 + i * panel_w + 6
        wx2 = x1 + (i + 1) * panel_w - 6
        draw.rectangle([wx1, win_y1, wx2, win_y2], fill=p["window"])


# ── House ─────────────────────────────────────────────────────────────────────
#
# Structure (floors = number of storeys, 1–3):
#
#      /\        ← roof triangle (always same pitch)
#     /  \
#    /    \
#   ┌──────┐
#   │ □  □ │    ← 2 windows per floor
#   │  ┌┐  │    ← door (ground floor only)
#   └──────┘

HOUSE_STOREY_H = 80  # px per storey
HOUSE_BASE_W   = 280  # medium house width


def _house(draw: ImageDraw.ImageDraw, floors: int, sm: float, p: dict) -> None:
    floors = max(1, min(floors, 3))
    cx = CANVAS_W // 2

    w = int(HOUSE_BASE_W * sm)
    wall_h = floors * HOUSE_STOREY_H
    roof_h = int(w * 0.40)           # fixed roof pitch ratio

    x1 = cx - w // 2;  x2 = cx + w // 2
    wall_y1 = GROUND_Y - wall_h;    wall_y2 = GROUND_Y
    roof_top_y = wall_y1 - roof_h

    _shadow(draw, cx, w // 2, p)

    # Walls
    draw.rectangle([x1, wall_y1, x2, wall_y2], fill=p["facade_a"])

    # Horizontal floor lines
    for f in range(1, floors):
        fy = GROUND_Y - f * HOUSE_STOREY_H
        draw.line([(x1, fy), (x2, fy)], fill=p["mullion"], width=2)

    # Roof
    draw.polygon(
        [(x1 - 14, wall_y1), (cx, roof_top_y), (x2 + 14, wall_y1)],
        fill=p["roof"],
    )
    # Roof outline
    draw.line(
        [(x1 - 14, wall_y1), (cx, roof_top_y), (x2 + 14, wall_y1)],
        fill=p["mullion"], width=2,
    )

    # Windows — 2 per storey
    win_w = int(w * 0.18);  win_h = int(HOUSE_STOREY_H * 0.48)
    win_margin_x = int(w * 0.18)
    for f in range(floors):
        fy_bot = GROUND_Y - f * HOUSE_STOREY_H
        fy_top = fy_bot - HOUSE_STOREY_H
        win_y1 = fy_top + int(HOUSE_STOREY_H * 0.22)
        win_y2 = win_y1 + win_h
        # Left window
        draw.rectangle([x1 + win_margin_x, win_y1, x1 + win_margin_x + win_w, win_y2], fill=p["window"])
        # Right window
        draw.rectangle([x2 - win_margin_x - win_w, win_y1, x2 - win_margin_x, win_y2], fill=p["window"])

    # Door (ground floor, centered)
    door_w = int(w * 0.14);  door_h = int(HOUSE_STOREY_H * 0.64)
    door_x1 = cx - door_w // 2;  door_x2 = cx + door_w // 2
    door_y2 = GROUND_Y;          door_y1 = door_y2 - door_h
    draw.rectangle([door_x1, door_y1, door_x2, door_y2], fill=p["mullion"])

    # Chimney for traditional brick
    if p["facade_a"] == PALETTES["traditional_brick"]["facade_a"]:
        ch_w = int(w * 0.07);  ch_h = int(roof_h * 0.65)
        ch_x = cx + int(w * 0.18)
        draw.rectangle(
            [ch_x, roof_top_y + int(roof_h * 0.1), ch_x + ch_w, wall_y1],
            fill=p["podium"],
        )


# ── Suburban building ──────────────────────────────────────────────────────────
#
# Mid-rise (2–15 floors). Wider than a skyscraper, flatter profile.
# Same horizontal floor bands as skyscraper, no setback, flat roof.
#
SUBURBAN_FLOOR_H = 18  # slightly taller floors (commercial scale)
SUBURBAN_BASE_W  = 360  # medium suburban width


def _suburban(draw: ImageDraw.ImageDraw, floors: int, sm: float, p: dict) -> None:
    floors = max(2, min(floors, 15))
    cx = CANVAS_W // 2
    w = int(SUBURBAN_BASE_W * sm)

    PODIUM_FLOORS = min(2, floors)
    podium_h = PODIUM_FLOORS * SUBURBAN_FLOOR_H
    bldg_h = floors * SUBURBAN_FLOOR_H

    if GROUND_Y - bldg_h < 80:
        floors = (GROUND_Y - 80) // SUBURBAN_FLOOR_H
        bldg_h = floors * SUBURBAN_FLOOR_H
        podium_h = min(PODIUM_FLOORS, floors) * SUBURBAN_FLOOR_H

    x1 = cx - w // 2;  x2 = cx + w // 2
    b_y1 = GROUND_Y - bldg_h
    p_y1 = GROUND_Y - podium_h

    _shadow(draw, cx, w // 2 + 10, p)

    # Podium
    draw.rectangle([x1 - 16, p_y1, x2 + 16, GROUND_Y], fill=p["podium"])

    # Upper floors
    BAYS = max(3, w // 90)          # number of vertical bays (piers between them)
    bay_w = w // BAYS

    for i in range(PODIUM_FLOORS, floors):
        fy2 = GROUND_Y - i * SUBURBAN_FLOOR_H
        fy1 = fy2 - SUBURBAN_FLOOR_H
        color = p["facade_a"] if i % 2 == 0 else p["facade_b"]
        draw.rectangle([x1, fy1, x2, fy2], fill=color)

        # Two windows per bay
        for bay in range(BAYS):
            bx1 = x1 + bay * bay_w
            bx2 = bx1 + bay_w
            win_y1 = fy1 + int(SUBURBAN_FLOOR_H * 0.14)
            win_y2 = fy1 + int(SUBURBAN_FLOOR_H * 0.80)
            # Left window in bay
            wx1 = bx1 + int(bay_w * 0.08)
            wx2 = bx1 + int(bay_w * 0.44)
            draw.rectangle([wx1, win_y1, wx2, win_y2], fill=p["window"])
            # Right window in bay
            wx1 = bx1 + int(bay_w * 0.56)
            wx2 = bx1 + int(bay_w * 0.92)
            draw.rectangle([wx1, win_y1, wx2, win_y2], fill=p["window"])

    # Vertical piers between bays
    for bay in range(1, BAYS):
        px = x1 + bay * bay_w
        draw.line([(px, b_y1), (px, p_y1)], fill=p["mullion"], width=3)

    # Horizontal floor lines
    for i in range(PODIUM_FLOORS, floors + 1):
        fy = GROUND_Y - i * SUBURBAN_FLOOR_H
        draw.line([(x1, fy), (x2, fy)], fill=p["mullion"], width=1)

    # Parapet / flat roof
    parapet_h = max(10, int(w * 0.028))
    draw.rectangle([x1, b_y1 - parapet_h, x2, b_y1], fill=p["roof"])
    # Cornice overhang
    draw.rectangle([x1 - 8, b_y1, x2 + 8, b_y1 + 4], fill=p["roof"])

    # Podium windows (lobby level)
    _podium_windows(draw, x1 - 16, p_y1, x2 + 16, GROUND_Y, p)
