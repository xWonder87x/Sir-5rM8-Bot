"""PNG charts for /serverstatus (occupancy + daily availability + hour heatmap)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

# Discord dark theme + green/red uptime (https://discord.com brand colors)
_BG = (49, 51, 56)  # #313338
_PANEL = (43, 45, 49)  # #2B2D31
_TEXT = (242, 243, 245)
_MUTED = (148, 155, 164)
_TRACK = (56, 58, 64)
_GREEN = (35, 165, 89)  # online
_YELLOW = (240, 178, 50)  # idle
_RED = (242, 63, 67)  # dnd
_CELL_UP = _GREEN
_HEAT = [
    (35, 165, 89),  # always up
    (80, 175, 72),
    (148, 186, 58),
    (240, 178, 50),
    (241, 128, 48),
    (237, 66, 69),
    (218, 45, 52),  # full hour down
]
_WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_DAILY_DAYS = 12


def _font(size: int, *, mono: bool = False) -> ImageFont.ImageFont:
    names = (
        ("DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
        if mono
        else ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    for path in names:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        ts = value
    else:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _lerp_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _gradient_at(stops: list[tuple[int, int, int]], t: float) -> tuple[int, int, int]:
    """t=0 first stop, t=1 last stop; interpolates between adjacent stops."""
    t = max(0.0, min(1.0, float(t)))
    if len(stops) == 1:
        return stops[0]
    scaled = t * (len(stops) - 1)
    i = min(int(scaled), len(stops) - 2)
    return _lerp_rgb(stops[i], stops[i + 1], scaled - i)


def _round_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    fill: tuple[int, int, int],
    radius: float,
) -> None:
    x0, y0, x1, y1 = box
    w, h = max(0.0, x1 - x0), max(0.0, y1 - y0)
    if w < 1 or h < 1:
        return
    r = max(1, min(int(radius), int(min(w, h) / 2)))
    draw.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=fill)


def _occupancy_color(ratio: float) -> tuple[int, int, int]:
    if ratio < 0.5:
        return _GREEN
    if ratio < 0.85:
        return _YELLOW
    return _RED


def _uptime_color(pct: float) -> tuple[int, int, int]:
    if pct >= 99:
        return _GREEN
    if pct >= 95:
        return _YELLOW
    return _RED


def _day_block_color(avg: float) -> tuple[int, int, int]:
    """Color a day by downtime minutes. 15 min and 45 min are distinct; full red ~3h down."""
    downtime_min = max(0.0, (100.0 - float(avg)) / 100.0 * 24.0 * 60.0)
    t = min(1.0, downtime_min / 180.0) ** 0.75
    return _gradient_at(_HEAT, t)


def _heat_color(uptime_pct: float) -> tuple[int, int, int]:
    """Hour cell: 0 min down = green, 15 min = yellow-green, 45 min = orange-red, 60 min = red."""
    downtime_frac = max(0.0, min(1.0, (100.0 - float(uptime_pct)) / 100.0))
    return _gradient_at(_HEAT, downtime_frac)


def _history_points(
    uptime_history: Sequence[tuple[datetime, float]] | Sequence[dict],
) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for row in uptime_history:
        try:
            if isinstance(row, dict):
                ts = _parse_ts(row.get("timestamp") or row.get("sampled_at"))
                pct = float(row.get("uptime") if row.get("uptime") is not None else row.get("value"))
            else:
                ts, pct = row[0], float(row[1])
                if not isinstance(ts, datetime):
                    ts = _parse_ts(ts)
                else:
                    ts = _parse_ts(ts)
            points.append((ts, max(0.0, min(100.0, pct))))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    points.sort(key=lambda p: p[0])
    return points


def _daily_averages(
    points: list[tuple[datetime, float]],
    *,
    end: datetime,
    days: int = _DAILY_DAYS,
) -> list[tuple[datetime, float | None]]:
    end_day = end.astimezone(timezone.utc).date()
    buckets: dict = {}
    for ts, pct in points:
        buckets.setdefault(ts.date(), []).append(pct)
    out: list[tuple[datetime, float | None]] = []
    for i in range(days - 1, -1, -1):
        day = end_day - timedelta(days=i)
        vals = buckets.get(day)
        avg = sum(vals) / len(vals) if vals else None
        noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
        out.append((noon, avg))
    return out


def _week_hour_grid(
    points: list[tuple[datetime, float]],
    *,
    end: datetime,
) -> list[list[float | None]]:
    """7 rows (Sun=0) x 24 hours for the last 7 UTC days ending at `end`."""
    end = end.astimezone(timezone.utc)
    start = end - timedelta(days=7)
    grid: list[list[list[float]]] = [[[] for _ in range(24)] for _ in range(7)]
    for ts, pct in points:
        if ts < start or ts > end:
            continue
        grid[ts.isoweekday() % 7][ts.hour].append(pct)
    return [
        [sum(cell) / len(cell) if cell else None for cell in row]
        for row in grid
    ]


def render_server_status_chart(
    *,
    session_name: str,
    num_players: int,
    max_players: int,
    uptime_history: Sequence[tuple[datetime, float]] | Sequence[dict] = (),
    history_days: int = 7,
    uptime_7: float | None = None,
    uptime_30: float | None = None,
    uptime_90: float | None = None,
    status_message: str | None = None,
) -> bytes:
    """Occupancy bar, 7/30/90 chips, daily availability strip, week×hour heatmap."""
    width, height = 800, 540
    img = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(img)
    title_font = _font(18)
    label_font = _font(13)
    small_font = _font(11)
    mono = _font(11, mono=True)

    title = (session_name or "Server")[:70]
    draw.text((24, 16), title, fill=_TEXT, font=title_font)

    ox, oy, ow, oh = 24, 48, width - 48, 72
    draw.rounded_rectangle((ox, oy, ox + ow, oy + oh), radius=10, fill=_PANEL)
    draw.text((ox + 16, oy + 8), "PLAYERS", fill=_MUTED, font=mono)
    max_p = max(int(max_players) or 1, 1)
    cur = max(0, int(num_players))
    ratio = min(cur / max_p, 1.0)
    bar_x, bar_y = ox + 16, oy + 30
    bar_w, bar_h = ow - 32, 16
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=5, fill=_TRACK)
    fill_w = max(int(bar_w * ratio), 2 if cur > 0 else 0)
    if fill_w:
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
            radius=5,
            fill=_occupancy_color(ratio),
        )
    draw.text((ox + 16, oy + 50), f"{cur} / {max_p}  ({int(ratio * 100)}% full)", fill=_TEXT, font=small_font)

    uy = 132
    chip_w = (width - 48 - 16) // 3
    for i, (label, val) in enumerate((("7d", uptime_7), ("30d", uptime_30), ("90d", uptime_90))):
        cx = 24 + i * (chip_w + 8)
        draw.rounded_rectangle((cx, uy, cx + chip_w, uy + 40), radius=8, fill=_PANEL)
        draw.text((cx + 12, uy + 5), f"UPTIME {label.upper()}", fill=_MUTED, font=mono)
        shown = "n/a" if val is None else f"{val:.2f}%"
        color = _MUTED if val is None else _uptime_color(val)
        draw.text((cx + 12, uy + 20), shown, fill=color, font=label_font)

    points = _history_points(uptime_history)
    end = points[-1][0] if points else datetime.now(timezone.utc)

    # --- Daily availability ---
    dy = 184
    draw.text((24, dy), "DAILY AVAILABILITY", fill=_MUTED, font=mono)
    daily = _daily_averages(points, end=end, days=_DAILY_DAYS)
    gap = 8
    block_w = int((width - 48 - gap * (_DAILY_DAYS - 1)) / _DAILY_DAYS)
    block_h = 36
    by = dy + 22
    for i, (_day, avg) in enumerate(daily):
        x = 24 + i * (block_w + gap)
        color = _TRACK if avg is None else _day_block_color(avg)
        _round_box(draw, (x, by, x + block_w, by + block_h), color, block_h / 2)
    draw.text((24, by + block_h + 6), f"{_DAILY_DAYS - 1} DAYS AGO", fill=_MUTED, font=mono)
    today = "TODAY"
    tb = draw.textbbox((0, 0), today, font=mono)
    draw.text((width - 24 - (tb[2] - tb[0]), by + block_h + 6), today, fill=_MUTED, font=mono)

    # --- Week x hour heatmap ---
    hx, hy = 24, by + block_h + 32
    hw, hh = width - 48, height - hy - 24
    draw.rounded_rectangle((hx, hy, hx + hw, hy + hh), radius=10, fill=_PANEL)
    draw.text((hx + 16, hy + 10), "LAST 7 DAYS  ·  HOUR OF DAY (UTC)", fill=_MUTED, font=mono)

    grid = _week_hour_grid(points, end=end)
    label_w = 40
    plot_l = hx + 16 + label_w
    plot_t = hy + 32
    plot_r = hx + hw - 16
    legend_h = 28
    plot_b = hy + hh - 20 - legend_h
    cell_w = (plot_r - plot_l) / 24.0
    cell_h = (plot_b - plot_t) / 7.0

    if not points:
        msg = status_message or "Uptime history unavailable."
        bbox = draw.textbbox((0, 0), msg, font=label_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            (plot_l + int((plot_r - plot_l - tw) / 2), plot_t + int((plot_b - plot_t) / 2) - 8),
            msg,
            fill=_MUTED,
            font=label_font,
        )
    else:
        for r, name in enumerate(_WEEKDAYS):
            y = plot_t + r * cell_h
            draw.text((hx + 12, y + cell_h / 2 - 6), name, fill=_MUTED, font=mono)
            for hour in range(24):
                x = plot_l + hour * cell_w
                val = grid[r][hour]
                color = _CELL_UP if val is None else _heat_color(val)
                pad_x, pad_y = 2.0, 1.8
                inner = (x + pad_x, y + pad_y, x + cell_w - pad_x, y + cell_h - pad_y)
                _round_box(draw, inner, color, 7)
        for hour, label in ((0, "00"), (6, "06"), (12, "12"), (18, "18")):
            x = plot_l + hour * cell_w
            draw.text((x, plot_b + 2), label, fill=_MUTED, font=mono)

    # Legend
    ly = hy + hh - 22
    draw.text((hx + 16, ly), "ALWAYS UP", fill=_MUTED, font=mono)
    sw, sh = 16, 12
    scale_x = hx + 110
    steps = 12
    for i in range(steps):
        col = _gradient_at(_HEAT, i / (steps - 1))
        _round_box(
            draw,
            (scale_x + i * (sw + 2), ly + 1, scale_x + i * (sw + 2) + sw, ly + 1 + sh),
            col,
            4,
        )
    down = "FULL HOUR DOWN"
    db = draw.textbbox((0, 0), down, font=mono)
    draw.text((hx + hw - 16 - (db[2] - db[0]), ly), down, fill=_MUTED, font=mono)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
