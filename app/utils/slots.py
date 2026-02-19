from __future__ import annotations

from typing import Any


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
        elif isinstance(value, list):
            original_len = len(value)
            value = clamp_list(value, rules.get("max_items"))
            if len(value) != original_len:
                warnings.append(f"{key} truncated to {rules.get('max_items')} items")
            if rules.get("max_chars_per_item"):
                trimmed = []
                for item in value:
                    trimmed_item = clamp_text(item, rules.get("max_chars_per_item"))
                    if trimmed_item != item:
                        warnings.append(f"{key} item truncated to {rules.get('max_chars_per_item')} chars")
                    trimmed.append(trimmed_item)
                value = trimmed

        sanitized[key] = value

    return sanitized, warnings
