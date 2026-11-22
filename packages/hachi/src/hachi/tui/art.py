"""ASCII art for the Hachi brand — the loyal loop.

The loyal loop is the terminal avatar of the hachi mark: a thick ASCII
infinity / figure-8 (two lobes side by side) rendered as a Rich ``Text``
block with per-cell coloring.

The motif encodes the brand promise:
  8 = ∞ = always on — "hachi" (八) means eight in Japanese.
  The loop never ends; hachi is always with you.

Colors come from the loop palette in ``hachi.tui.theme``:

  HACHI_BODY        — torii red, the main loop mass
  HACHI_BODY_BRIGHT — brighter red, the right-lobe highlight / crossing point
  HACHI_EYE_CREAM   — bone/cream, the glint inside each lobe
  HACHI_TONGUE      — amber warm accent at the loop ends

Rendering is deterministic (no random, no time) and generated on demand.
"""

from __future__ import annotations

import math

from rich.text import Text

from hachi.tui import theme

_BLOCK = "█"

# ---------------------------------------------------------------------------
# Loyal loop geometry helpers
# ---------------------------------------------------------------------------


def _lemniscate_r(theta: float, a: float) -> float:
    """Polar radius of a lemniscate of Bernoulli: r² = a² · cos(2θ).

    Returns 0 when cos(2θ) < 0 (outside the figure-8 region).
    """
    cos2 = math.cos(2 * theta)
    if cos2 < 0:
        return 0.0
    return a * math.sqrt(cos2)


def ouroboros(width: int = 52, height: int = 17) -> Text:
    """Return the Hachi loyal loop as a colored Rich ``Text`` block.

    Draws a thick ASCII infinity / figure-8 (lemniscate of Bernoulli) in the
    four loop-palette colors.  The loop fills a ``width × height`` character
    grid; cells are roughly 2× taller than wide, so the y-axis is scaled by
    0.5 to keep the shape round.

    The crossing point at the centre is accented with ``HACHI_BODY_BRIGHT``.
    Cream glints sit inside each lobe.  An amber warm accent traces the
    outermost rim on both sides.
    """
    # Aspect correction: terminal cells are ~2× taller than wide.
    aspect = 0.5

    # Map the character grid to [-1, 1] in x and [-aspect, aspect] in y.
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0

    # Lemniscate scale: a = 0.9 fills most of the grid (in normalised coords).
    a = 0.9

    # Thickness bands (in normalised polar radius away from the curve).
    OUTER_THICK = 0.22  # outer edge of the loop mass
    INNER_THICK = 0.07  # inner hollow (makes the loop ring-like)
    BRIGHT_BAND = 0.13  # how wide the bright-red centre-crossing band is

    # Pre-compute a dense set of (px, py) curve points in grid coords.
    _N_THETA = 2000
    _curve_pts: list[tuple[float, float]] = []
    for i in range(_N_THETA):
        th = (i / _N_THETA) * 2 * math.pi
        r = _lemniscate_r(th, a)
        if r <= 0:
            continue
        nx = r * math.cos(th)  # [-1, 1]
        ny = r * math.sin(th) * aspect  # [-aspect, aspect] → squash for cells
        gx = cx + nx * cx
        gy = cy + ny / aspect * cy
        _curve_pts.append((gx, gy))

    def _min_dist_to_curve(gx: float, gy: float) -> tuple[float, float]:
        """Return (min_dist, best_theta) to the nearest curve point."""
        best_d = 1e9
        best_th = 0.0
        for i, (px, py) in enumerate(_curve_pts):
            d = math.hypot(gx - px, gy - py)
            if d < best_d:
                best_d = d
                best_th = (i / _N_THETA) * 2 * math.pi
        return best_d, best_th

    # Build the grid.
    grid: list[list[str | None]] = [[None] * width for _ in range(height)]

    for row in range(height):
        for col in range(width):
            dist, best_th = _min_dist_to_curve(float(col), float(row))

            if dist > OUTER_THICK * (width / 2):
                continue  # outside the loop entirely

            if dist < INNER_THICK * (width / 2):
                continue  # inside the hollow core

            # Determine which lobe: right lobe = theta near 0/2π, left = near π.
            # The crossing at θ = π/2 and 3π/2 is the centre bridge.
            norm_th = best_th % (2 * math.pi)
            at_crossing = abs(norm_th - math.pi / 2) < 0.38 or abs(norm_th - 3 * math.pi / 2) < 0.38

            # Cream glints: small region inside each lobe, away from the crossing.
            in_right_lobe = norm_th < 0.6 or norm_th > 2 * math.pi - 0.6
            in_left_lobe = abs(norm_th - math.pi) < 0.6

            # Amber accent: the very outermost rim cells.
            at_rim = dist > OUTER_THICK * (width / 2) * 0.84

            if at_rim:
                grid[row][col] = theme.HACHI_TONGUE
            elif at_crossing:
                grid[row][col] = theme.HACHI_BODY_BRIGHT
            elif (in_right_lobe or in_left_lobe) and dist < BRIGHT_BAND * (width / 2):
                grid[row][col] = theme.HACHI_EYE_CREAM
            else:
                grid[row][col] = theme.HACHI_BODY

    text = Text()
    for row in range(height):
        for col in range(width):
            color = grid[row][col]
            text.append(_BLOCK if color else " ", style=color or "")
        if row < height - 1:
            text.append("\n")
    return text


# Alias so callers can also import ``loyal_loop`` for clarity.
loyal_loop = ouroboros
