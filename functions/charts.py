"""PNG charts for /serverstatus (occupancy bar + player history)."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        ts = value
    else:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _occupancy_color(ratio: float) -> tuple[int, int, int]:
    if ratio < 0.5:
        return (46, 204, 113)
    if ratio < 0.85:
        return (241, 196, 15)
    return (231, 76, 60)


def render_server_status_chart(
    *,
    session_name: str,
    num_players: int,
    max_players: int,
    history: Sequence[dict],
    history_hours: int = 24,
) -> bytes:
    """
    Build a single PNG: occupancy bar on top, player-count line chart below.
    history items: {sampled_at, num_players, max_players}
    """
    width, height = 800, 460
    bg = (24, 26, 32)
    panel = (34, 37, 46)
    text = (230, 232, 238)
    muted = (150, 155, 165)
    grid = (55, 60, 72)
    line = (88, 166, 255)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    title_font = _font(20)
    label_font = _font(14)
    small_font = _font(12)

    title = (session_name or "Server")[:70]
    draw.text((24, 16), title, fill=text, font=title_font)

    # --- Occupancy panel ---
    ox, oy, ow, oh = 24, 52, width - 48, 90
    draw.rounded_rectangle((ox, oy, ox + ow, oy + oh), radius=10, fill=panel)
    draw.text((ox + 16, oy + 12), "Players", fill=muted, font=label_font)

    max_p = max(int(max_players) or 1, 1)
    cur = max(0, int(num_players))
    ratio = min(cur / max_p, 1.0)
    bar_x, bar_y = ox + 16, oy + 42
    bar_w, bar_h = ow - 32, 22
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=6,
        fill=(45, 49, 58),
    )
    fill_w = max(int(bar_w * ratio), 2 if cur > 0 else 0)
    if fill_w:
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
            radius=6,
            fill=_occupancy_color(ratio),
        )
    draw.text(
        (ox + 16, oy + 68),
        f"{cur} / {max_p}  ({int(ratio * 100)}% full)",
        fill=text,
        font=label_font,
    )

    # --- History panel ---
    hx, hy, hw, hh = 24, 160, width - 48, height - 184
    draw.rounded_rectangle((hx, hy, hx + hw, hy + hh), radius=10, fill=panel)
    draw.text(
        (hx + 16, hy + 12),
        f"Player count — last {history_hours}h",
        fill=muted,
        font=label_font,
    )

    points: list[tuple[datetime, int]] = []
    for row in history:
        try:
            points.append((_parse_ts(row["sampled_at"]), int(row["num_players"])))
        except (KeyError, TypeError, ValueError):
            continue

    plot_l, plot_t = hx + 48, hy + 44
    plot_r, plot_b = hx + hw - 20, hy + hh - 36
    plot_w = plot_r - plot_l
    plot_h = plot_b - plot_t

    # Axes / grid
    y_max = max([p[1] for p in points] + [max_p, 1])
    for i in range(5):
        y = plot_t + int(plot_h * i / 4)
        draw.line((plot_l, y, plot_r, y), fill=grid, width=1)
        val = int(y_max * (1 - i / 4))
        draw.text((hx + 10, y - 7), str(val), fill=muted, font=small_font)
    draw.line((plot_l, plot_t, plot_l, plot_b), fill=grid, width=1)
    draw.line((plot_l, plot_b, plot_r, plot_b), fill=grid, width=1)

    if len(points) < 2:
        msg = "Collecting history… check back after a few samples."
        bbox = draw.textbbox((0, 0), msg, font=label_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (plot_l + (plot_w - tw) // 2, plot_t + plot_h // 2 - 8),
            msg,
            fill=muted,
            font=label_font,
        )
    else:
        t0, t1 = points[0][0], points[-1][0]
        span = max((t1 - t0).total_seconds(), 1.0)

        def xy(ts: datetime, players: int) -> tuple[int, int]:
            x = plot_l + int(((ts - t0).total_seconds() / span) * plot_w)
            y = plot_b - int((players / y_max) * plot_h)
            return x, y

        coords = [xy(ts, n) for ts, n in points]
        draw.line(coords, fill=line, width=3)
        for x, y in coords[:: max(1, len(coords) // 24)] + [coords[-1]]:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=line)

        # Time labels
        draw.text(
            (plot_l, plot_b + 8),
            t0.astimezone(timezone.utc).strftime("%H:%M UTC"),
            fill=muted,
            font=small_font,
        )
        end_label = t1.astimezone(timezone.utc).strftime("%H:%M UTC")
        end_bbox = draw.textbbox((0, 0), end_label, font=small_font)
        draw.text(
            (plot_r - (end_bbox[2] - end_bbox[0]), plot_b + 8),
            end_label,
            fill=muted,
            font=small_font,
        )

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
