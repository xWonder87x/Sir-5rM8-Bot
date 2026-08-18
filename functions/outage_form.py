"""Prefill Wildcard's ASA outage Google Form from a /serverstatus lookup."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import config
from functions.asa import query_server_number
from functions.server_status import ResolvedServer

# Discord link buttons reject URLs longer than this.
_BUTTON_URL_MAX = 512

_ENTRY_REGION = "472752241"
_ENTRY_MODE = "1873349371"
_ENTRY_MAP = "1678916340"
_ENTRY_NUMBER = "1668883225"
_ENTRY_DURATION = "1746633654"
_ENTRY_ISSUE = "639417572"
_ENTRY_EXTRA = "1489095573"
_ENTRY_DISCORD = "233908548"

_ISSUE_OFFLINE = "Offline/Down/Crashed"
_DURATION_0_30 = "0-30 minutes"
_DURATION_31_60 = "31 minutes - 1 hour"
_DURATION_1_3H = "1 hour - 3 hours"
_DURATION_3H_PLUS = "3 hours+"

_MAPS = {
    "theisland": "The Island",
    "scorchedearth": "Scorched Earth",
    "thecenter": "The Center",
    "aberration": "Aberration",
    "extinction": "Extinction",
    "astraeos": "Astraeos",
    "ragnarok": "Ragnarok",
    "valguero": "Valguero",
    "lostcolony": "Lost Colony",
    "genesis": "Genesis 1",
    "genesis1": "Genesis 1",
    "svartalfheim": "Svartalfheim",
    "reverence": "Reverence",
    "asurvivethenight": "Survive The Night",
    "survivethenight": "Survive The Night",
    "lvlenclave": "Enclave",
    "enclave": "Enclave",
    "sotf": "SOTF",
    "survivalofthefittesttheisland": "SOTF",
    "forglar": "Forglar",
    "bobsmissions": "ClubARK",
    "clubark": "ClubARK",
    "appalachia": "Appalachia",
    "appalachiaofficial": "Appalachia",
    "althemia": "Althemia",
    "nyrandil": "Nyrandil",
    "atlantis": "Atlantis",
    "tharat": "Tharat",
    "eden": "Eden",
    "edenpremium": "Eden",
    "thevolcano": "The Volcano",
    "lostcity": "Lost City",
    "protocol": "Lost Protocol",
    "lostprotocol": "Lost Protocol",
}


def _norm(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def region_from_name(session_name: str) -> str | None:
    token = (session_name or "").split("-", 1)[0].strip().upper()
    if token in ("NA", "EU", "OC"):
        return token
    if token == "ASIA":
        return "Asia"
    return None


def mode_from_name(session_name: str) -> str | None:
    name = (session_name or "").upper()
    if "SMALLTRIBE" in name:
        return "Small Tribes"
    if "ARKPOCALYPSE" in name:
        return "ARKpocalypse"
    if "SOTF" in name:
        return "SOTF"
    if "MODDED" in name:
        return "Modded"
    if "-PVE-" in name or name.startswith("PVE-") or "-PVE " in name:
        return "PVE"
    if "-PVP-" in name or name.startswith("PVP-"):
        return "PVP"
    return None


def map_from_name(map_name: str) -> str | None:
    key = _norm((map_name or "").replace("_WP", ""))
    return _MAPS.get(key)


def server_number_from_resolved(resolved: ResolvedServer) -> str | None:
    for candidate in (resolved.server_key, resolved.query, resolved.session_name):
        number = query_server_number(str(candidate or ""))
        if number:
            return number
    return None


def _history_step_minutes(points: list[tuple[datetime, float]]) -> int:
    if len(points) >= 2:
        delta = (points[-1][0] - points[-2][0]).total_seconds() / 60.0
        if delta >= 1:
            return int(round(delta))
    return max(1, int(config.BM_UPTIME_RESOLUTION_MINUTES))


def current_outage_minutes(
    history: list[tuple[datetime, float]] | None,
    *,
    resolution_minutes: int | None = None,
) -> float | None:
    """Length of the current downtime streak from BM uptime %, newest first."""
    points = sorted(
        ((ts, float(pct)) for ts, pct in (history or [])),
        key=lambda p: p[0],
    )
    if not points:
        return None
    step = float(resolution_minutes if resolution_minutes is not None else _history_step_minutes(points))
    total = 0.0
    for _ts, pct in reversed(points):
        down = max(0.0, min(1.0, (100.0 - pct) / 100.0))
        if down <= 0.005:
            break
        total += down * step
        if down < 0.995:
            break
    return total if total > 0 else None


def duration_choice_from_history(
    history: list[tuple[datetime, float]] | None,
    *,
    resolution_minutes: int | None = None,
) -> str:
    minutes = current_outage_minutes(history, resolution_minutes=resolution_minutes)
    if minutes is None or minutes <= 30:
        return _DURATION_0_30
    if minutes <= 60:
        return _DURATION_31_60
    if minutes <= 180:
        return _DURATION_1_3H
    return _DURATION_3H_PLUS


def _additional_info(resolved: ResolvedServer) -> str:
    bits = [resolved.session_name] if resolved.session_name and resolved.session_name != "Unknown" else []
    if resolved.ip and resolved.ip not in ("—", "-"):
        bits.append(f"server IP {resolved.ip}")
    if resolved.platform and resolved.platform not in ("—", "-"):
        bits.append(resolved.platform)
    if resolved.query:
        bits.append(f"query {resolved.query}")
    minutes = current_outage_minutes(resolved.bm.history if resolved.bm else None)
    if minutes:
        bits.append(f"BM down ~{int(round(minutes))}m")
    return " | ".join(bits)[:180]


def _encode(base: str, fields: dict[str, str]) -> str:
    split = urlsplit(base)
    params = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if k != "usp"]
    params.append(("usp", "pp_url"))
    for entry_id, value in fields.items():
        if value:
            params.append((f"entry.{entry_id}", value))
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(params), split.fragment))


def build_outage_report_url(
    resolved: ResolvedServer,
    *,
    discord_username: str | None = None,
    base_url: str | None = None,
) -> str:
    """Prefill region, mode, map, number, issue, extra; never the reporter's public IP."""
    base = (base_url or config.OUTAGE_REPORT_URL or "").strip()
    fields: dict[str, str] = {
        _ENTRY_REGION: region_from_name(resolved.session_name) or "",
        _ENTRY_MODE: mode_from_name(resolved.session_name) or "",
        _ENTRY_MAP: map_from_name(resolved.map_name) or "",
        _ENTRY_NUMBER: server_number_from_resolved(resolved) or "",
        _ENTRY_DURATION: duration_choice_from_history(resolved.bm.history if resolved.bm else None),
        _ENTRY_ISSUE: _ISSUE_OFFLINE,
        _ENTRY_EXTRA: _additional_info(resolved),
        _ENTRY_DISCORD: (discord_username or "").strip(),
    }
    # Platform is a single-choice on a crossplay cluster — leave it for the player.
    url = _encode(base, fields)
    if len(url) <= _BUTTON_URL_MAX:
        return url
    fields[_ENTRY_EXTRA] = ""
    url = _encode(base, fields)
    if len(url) <= _BUTTON_URL_MAX:
        return url
    fields[_ENTRY_DISCORD] = ""
    return _encode(base, fields)
