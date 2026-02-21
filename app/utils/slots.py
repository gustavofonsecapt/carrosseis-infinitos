from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Threshold: if a slot exceeds the limit by more than this ratio, trigger auto-rewrite
COMPRESS_OVERFLOW_RATIO = 0.15


def summarize_slot_constraints(slot_schema: dict[str, Any]) -> str:
    lines: list[str] = []
    slots = slot_schema.get("slots", {})
    for key, meta in slots.items():
        constraints: list[str] = []
        if max_chars := meta.get("max_chars"):
            constraints.append(f"max {max_chars} chars")
        if max_lines := meta.get("max_lines"):
            constraints.append(f"max {max_lines} lines")
        if max_items := meta.get("max_items"):
            constraints.append(f"max {max_items} items")
        if max_chars_item := meta.get("max_chars_per_item"):
            constraints.append(f"max {max_chars_item} chars/item")
        desc = meta.get("description")
        constraint_str = ", ".join(constraints)
        lines.append(f"- {key}: {desc or ''} ({constraint_str})".strip())
    return "\n".join(lines)


def clamp_text(value: str, max_chars: int | None) -> str:
    if max_chars and len(value) > max_chars:
        return value[:max_chars].rstrip()
    return value


def clamp_list(items: list[str], max_items: int | None) -> list[str]:
    if max_items is not None:
        return items[:max_items]
    return items


def enforce_slot_limits(payload: dict[str, Any], slot_schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return sanitized payload + list of warnings."""
    warnings: list[str] = []
    slots = slot_schema.get("slots", {})
    sanitized: dict[str, Any] = {}

    for key, value in payload.items():
        rules = slots.get(key)
        if not rules:
            sanitized[key] = value
            continue

        if isinstance(value, str):
            original = value
            value = clamp_text(value, rules.get("max_chars"))
            if value != original:
                warnings.append(f"{key} truncated to {rules.get('max_chars')} chars")
                logger.warning("Slot '%s' truncated: %d -> %d chars", key, len(original), len(value))
        elif isinstance(value, list):
            original_len = len(value)
            value = clamp_list(value, rules.get("max_items"))
            if len(value) != original_len:
                warnings.append(f"{key} truncated to {rules.get('max_items')} items")
                logger.warning("Slot '%s' list truncated: %d -> %d items", key, original_len, len(value))
            if rules.get("max_chars_per_item"):
                trimmed = []
                for item in value:
                    trimmed_item = clamp_text(item, rules.get("max_chars_per_item"))
                    if trimmed_item != item:
                        warnings.append(f"{key} item truncated to {rules.get('max_chars_per_item')} chars")
                        logger.warning("Slot '%s' item truncated: %d -> %d chars", key, len(item), len(trimmed_item))
                    trimmed.append(trimmed_item)
                value = trimmed

        sanitized[key] = value

    return sanitized, warnings


def detect_overflow_slots(payload: dict[str, Any], slot_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Detect slots that overflow beyond COMPRESS_OVERFLOW_RATIO threshold.
    
    Returns dict of slot_name -> {"value": ..., "max_chars": ..., "overflow_pct": ...}
    for slots that need auto-rewrite.
    """
    overflows: dict[str, dict[str, Any]] = {}
    slots = slot_schema.get("slots", {})

    for key, value in payload.items():
        rules = slots.get(key)
        if not rules:
            continue

        if isinstance(value, str):
            max_chars = rules.get("max_chars")
            if max_chars and len(value) > max_chars:
                overflow_pct = (len(value) - max_chars) / max_chars
                if overflow_pct > COMPRESS_OVERFLOW_RATIO:
                    overflows[key] = {
                        "value": value,
                        "max_chars": max_chars,
                        "overflow_pct": round(overflow_pct, 2),
                    }
        elif isinstance(value, list):
            max_chars_per_item = rules.get("max_chars_per_item")
            if max_chars_per_item:
                for i, item in enumerate(value):
                    if len(item) > max_chars_per_item:
                        overflow_pct = (len(item) - max_chars_per_item) / max_chars_per_item
                        if overflow_pct > COMPRESS_OVERFLOW_RATIO:
                            overflows[f"{key}[{i}]"] = {
                                "value": item,
                                "max_chars": max_chars_per_item,
                                "overflow_pct": round(overflow_pct, 2),
                            }

    return overflows


def build_composition_hints(slot_schema: dict[str, Any]) -> str:
    """Generate composition hints based on slot schema to guide content strategy."""
    slots = slot_schema.get("slots", {})
    hints: list[str] = []

    has_bullets = "bullets" in slots
    has_body = "body" in slots
    bullets_meta = slots.get("bullets", {})
    body_meta = slots.get("body", {})

    if has_bullets and has_body:
        body_max = body_meta.get("max_chars", 999)
        bullet_max_items = bullets_meta.get("max_items", 0)
        if bullet_max_items >= 3 and body_max <= 120:
            hints.append("Prefer bullets (3-5 items) over paragraph — body space is limited.")
        elif body_max >= 180:
            hints.append("You may use a short paragraph OR bullets, but keep it concise.")
    elif has_bullets:
        hints.append("Use bullet points. Keep each item punchy and actionable.")

    headline_meta = slots.get("headline") or slots.get("title")
    if headline_meta:
        max_c = headline_meta.get("max_chars", 60)
        if max_c <= 50:
            hints.append(f"Headline must be very short (max {max_c} chars). Prioritize impact.")

    return "\n".join(hints) if hints else ""


# ── Role-aware slot capabilities ────────────────────────────────────

# Slots that are considered "global" and available to all roles
_GLOBAL_SLOTS = {"brand", "number", "image", "footer_note", "page_counter"}

# Slots forbidden per role (safety net)
FORBIDDEN_SLOTS: dict[str, set[str]] = {
    "cover": {"body", "bullets", "cta_title", "cta_button", "cta_body", "cta", "subcta"},
    "body": {"cta_title", "cta_button", "cta_body", "cta", "subcta"},
    "cta": {"body", "bullets", "subtitle", "subhead", "kicker"},
    "frame": set(),
    "frame_cta": set(),
}


def derive_slot_capabilities(slot_schema: dict[str, Any]) -> dict[str, Any]:
    """Analyze a slot_schema and return feature flags for content strategy."""
    slots = slot_schema.get("slots", {})
    bullets_meta = slots.get("bullets", {})
    body_meta = slots.get("body", {})
    return {
        "supports_title": "title" in slots or "headline" in slots,
        "supports_subtitle": "subtitle" in slots or "subhead" in slots,
        "supports_kicker": "kicker" in slots,
        "supports_body": "body" in slots,
        "supports_bullets": "bullets" in slots,
        "supports_cta_title": "cta_title" in slots,
        "supports_cta_body": "cta_body" in slots,
        "supports_cta_button": "cta_button" in slots,
        "supports_brand": "brand" in slots,
        "supports_number": "number" in slots,
        "supports_image": "image" in slots,
        "title_key": "title" if "title" in slots else "headline",
        "subtitle_key": "subtitle" if "subtitle" in slots else "subhead",
        "bullets_strategy": bool(bullets_meta.get("max_items", 0) >= 3),
        "body_strategy": bool(body_meta.get("max_chars", 0) >= 100),
    }


def build_role_schema(role: str, caps: dict[str, Any], slot_schema: dict[str, Any]) -> str:
    """Generate a human-readable description of allowed fields per role.

    Used to inject into the OpenAI prompt so the model knows exactly
    which fields are required, optional, and forbidden for each role.
    """
    slots = slot_schema.get("slots", {})
    title_key = caps["title_key"]
    subtitle_key = caps["subtitle_key"]
    forbidden = FORBIDDEN_SLOTS.get(role, set())

    lines: list[str] = []
    required: list[str] = []
    optional: list[str] = []

    def _slot_desc(key: str) -> str:
        meta = slots.get(key, {})
        parts = [key]
        if mc := meta.get("max_chars"):
            parts.append(f"max {mc} chars")
        if mi := meta.get("max_items"):
            parts.append(f"max {mi} items")
        if mci := meta.get("max_chars_per_item"):
            parts.append(f"max {mci} chars/item")
        return f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]

    if role == "cover":
        if caps["supports_title"]:
            required.append(_slot_desc(title_key))
        if caps["supports_subtitle"]:
            optional.append(_slot_desc(subtitle_key))
        if caps["supports_kicker"]:
            optional.append(_slot_desc("kicker"))
        if caps["supports_brand"]:
            optional.append(_slot_desc("brand"))
        if caps["supports_number"]:
            optional.append(_slot_desc("number"))

    elif role == "body":
        if caps["supports_title"]:
            required.append(_slot_desc(title_key))
        if caps["supports_body"]:
            required.append(_slot_desc("body") + " — short paragraph")
        if caps["supports_bullets"]:
            optional.append(_slot_desc("bullets") + " — USE BULLETS to complement the paragraph")
        if caps["supports_brand"]:
            optional.append(_slot_desc("brand"))
        if caps["supports_number"]:
            optional.append(_slot_desc("number"))

    elif role == "cta":
        if caps["supports_cta_title"]:
            required.append(_slot_desc("cta_title"))
        elif caps["supports_title"]:
            required.append(_slot_desc(title_key))
        if caps["supports_cta_button"]:
            required.append(_slot_desc("cta_button"))
        elif "cta" in slots:
            required.append(_slot_desc("cta"))
        if caps["supports_cta_body"]:
            optional.append(_slot_desc("cta_body"))
        if "subcta" in slots:
            optional.append(_slot_desc("subcta"))
        if "signature" in slots:
            optional.append(_slot_desc("signature"))
        if caps["supports_brand"]:
            optional.append(_slot_desc("brand"))

    else:
        # frame / frame_cta — include all non-forbidden slots
        for key, meta in slots.items():
            if key in forbidden:
                continue
            if meta.get("required"):
                required.append(_slot_desc(key))
            else:
                optional.append(_slot_desc(key))

    lines.append(f"{role.upper()}:")
    if required:
        lines.append(f"  REQUIRED: {', '.join(required)}")
    if optional:
        lines.append(f"  OPTIONAL: {', '.join(optional)}")
    forbidden_names = sorted(forbidden & set(slots.keys()))
    if forbidden_names:
        lines.append(f"  FORBIDDEN: {', '.join(forbidden_names)}")
    return "\n".join(lines)


def strip_forbidden_slots(entry: dict[str, Any], role: str) -> list[str]:
    """Remove slots that are not allowed for a given role. Returns list of stripped keys."""
    forbidden = FORBIDDEN_SLOTS.get(role, set())
    stripped: list[str] = []
    for key in list(entry.keys()):
        if key in forbidden:
            entry.pop(key)
            stripped.append(key)
    return stripped
