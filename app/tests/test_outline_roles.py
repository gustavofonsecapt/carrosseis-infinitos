"""Tests for role-aware outline generation.

Validates that:
- Cover slides contain only hook/subtitle/brand/number (no body/bullets/cta)
- CTA slides contain only cta_title/cta_button/brand (no body/bullets)
- Body slides adapt bullets vs paragraph based on template slots
- All slots respect limits from slots.json
"""
from __future__ import annotations

import pytest

from app.utils.slots import (
    FORBIDDEN_SLOTS,
    build_role_schema,
    derive_slot_capabilities,
    strip_forbidden_slots,
    enforce_slot_limits,
)


# ── Sample slot schemas (mirroring real slots.json) ─────────────────

FAMILY_SLOTS = {
    "slots": {
        "brand": {"required": False, "max_chars": 32},
        "category": {"required": False, "max_chars": 32},
        "kicker": {"required": False, "max_chars": 32},
        "title": {"required": True, "max_chars": 68},
        "subtitle": {"required": False, "max_chars": 90},
        "body": {"required": False, "max_chars": 220},
        "bullets": {"required": False, "max_items": 5, "max_chars_per_item": 48},
        "number": {"required": False, "max_chars": 10},
        "image": {"required": False},
        "cta_title": {"required": False, "max_chars": 50},
        "cta_body": {"required": False, "max_chars": 180},
        "cta_button": {"required": False, "max_chars": 20},
        "footer_note": {"required": False, "max_chars": 32},
    }
}

CLASSIC_COVER_SLOTS = {
    "slots": {
        "kicker": {"required": False, "max_chars": 30},
        "headline": {"required": True, "max_chars": 60},
        "subhead": {"required": False, "max_chars": 90},
        "image": {"required": False},
    }
}

CLASSIC_BODY_SLOTS = {
    "slots": {
        "headline": {"required": True, "max_chars": 50},
        "body": {"required": False, "max_chars": 200},
        "bullets": {"required": False, "max_items": 5, "max_chars_per_item": 55},
        "support": {"required": False, "max_chars": 80},
        "image": {"required": False},
        "page_counter": {"required": False},
    }
}

CLASSIC_CTA_SLOTS = {
    "slots": {
        "headline": {"required": True, "max_chars": 50},
        "cta": {"required": True, "max_chars": 40},
        "subcta": {"required": False, "max_chars": 60},
        "signature": {"required": True, "max_chars": 40},
    }
}


# ── derive_slot_capabilities ───────────────────────────────────────

class TestDeriveSlotCapabilities:
    def test_family_slots_detected(self):
        caps = derive_slot_capabilities(FAMILY_SLOTS)
        assert caps["supports_title"] is True
        assert caps["supports_subtitle"] is True
        assert caps["supports_kicker"] is True
        assert caps["supports_body"] is True
        assert caps["supports_bullets"] is True
        assert caps["supports_cta_title"] is True
        assert caps["supports_cta_body"] is True
        assert caps["supports_cta_button"] is True
        assert caps["title_key"] == "title"
        assert caps["subtitle_key"] == "subtitle"
        assert caps["bullets_strategy"] is True
        assert caps["body_strategy"] is True

    def test_classic_cover_uses_headline(self):
        caps = derive_slot_capabilities(CLASSIC_COVER_SLOTS)
        assert caps["title_key"] == "headline"
        assert caps["subtitle_key"] == "subhead"
        assert caps["supports_body"] is False
        assert caps["supports_bullets"] is False

    def test_classic_cta_no_body(self):
        caps = derive_slot_capabilities(CLASSIC_CTA_SLOTS)
        assert caps["supports_body"] is False
        assert caps["supports_bullets"] is False
        assert caps["supports_cta_title"] is False  # classic uses "headline"


# ── strip_forbidden_slots ──────────────────────────────────────────

class TestStripForbiddenSlots:
    def test_cover_strips_body_and_cta(self):
        entry = {
            "n": 1, "role": "cover",
            "title": "Hook", "subtitle": "Sub",
            "body": "Should be removed",
            "bullets": ["also removed"],
            "cta_title": "removed",
            "cta_button": "removed",
        }
        stripped = strip_forbidden_slots(entry, "cover")
        assert "body" in stripped
        assert "bullets" in stripped
        assert "cta_title" in stripped
        assert "cta_button" in stripped
        assert "body" not in entry
        assert "bullets" not in entry
        assert "title" in entry
        assert "subtitle" in entry

    def test_cta_strips_body_and_bullets(self):
        entry = {
            "n": 8, "role": "cta",
            "cta_title": "CTA", "cta_button": "DM",
            "body": "removed", "bullets": ["removed"],
            "subtitle": "removed", "kicker": "removed",
        }
        stripped = strip_forbidden_slots(entry, "cta")
        assert "body" in stripped
        assert "bullets" in stripped
        assert "subtitle" in stripped
        assert "kicker" in stripped
        assert "cta_title" in entry
        assert "cta_button" in entry

    def test_body_strips_cta_fields(self):
        entry = {
            "n": 2, "role": "body",
            "title": "Point 1",
            "bullets": ["A", "B"],
            "cta_title": "should go",
            "cta_button": "should go",
        }
        stripped = strip_forbidden_slots(entry, "body")
        assert "cta_title" in stripped
        assert "cta_button" in stripped
        assert "title" in entry
        assert "bullets" in entry

    def test_body_keeps_body_and_bullets(self):
        entry = {
            "n": 3, "role": "body",
            "title": "Point",
            "body": "A paragraph",
            "bullets": ["item1"],
        }
        stripped = strip_forbidden_slots(entry, "body")
        assert stripped == []
        assert "body" in entry
        assert "bullets" in entry


# ── build_role_schema ──────────────────────────────────────────────

class TestBuildRoleSchema:
    def test_cover_schema_includes_title(self):
        caps = derive_slot_capabilities(FAMILY_SLOTS)
        schema = build_role_schema("cover", caps, FAMILY_SLOTS)
        assert "COVER:" in schema
        assert "title" in schema
        assert "FORBIDDEN" in schema
        assert "body" in schema.split("FORBIDDEN")[1]

    def test_body_schema_bullets_strategy(self):
        caps = derive_slot_capabilities(FAMILY_SLOTS)
        schema = build_role_schema("body", caps, FAMILY_SLOTS)
        assert "BODY:" in schema
        assert "BULLETS" in schema
        assert "FORBIDDEN" in schema

    def test_cta_schema(self):
        caps = derive_slot_capabilities(FAMILY_SLOTS)
        schema = build_role_schema("cta", caps, FAMILY_SLOTS)
        assert "CTA:" in schema
        assert "cta_title" in schema
        assert "cta_button" in schema


# ── Simulated fallback payload validation ──────────────────────────

class TestFallbackRoleCompliance:
    """Simulate what a role-aware fallback should produce and validate constraints."""

    def _make_cover(self) -> dict:
        return {"n": 1, "role": "cover", "title": "Hook headline", "subtitle": "Supporting text", "number": "01/08"}

    def _make_body(self, n: int) -> dict:
        return {"n": n, "role": "body", "title": f"Point {n-1}", "bullets": ["Insight A", "Insight B", "Insight C"], "number": f"{n:02d}/08"}

    def _make_cta(self) -> dict:
        return {"n": 8, "role": "cta", "cta_title": "Take action", "cta_button": "DM", "brand": ""}

    def test_cover_has_no_forbidden_slots(self):
        cover = self._make_cover()
        forbidden = FORBIDDEN_SLOTS["cover"]
        for key in forbidden:
            assert key not in cover, f"Cover should not have '{key}'"

    def test_cta_has_no_forbidden_slots(self):
        cta = self._make_cta()
        forbidden = FORBIDDEN_SLOTS["cta"]
        for key in forbidden:
            assert key not in cta, f"CTA should not have '{key}'"

    def test_body_has_content(self):
        body = self._make_body(2)
        has_content = "body" in body or "bullets" in body
        assert has_content, "Body must have either 'body' or 'bullets'"

    def test_body_has_no_cta(self):
        body = self._make_body(3)
        forbidden = FORBIDDEN_SLOTS["body"]
        for key in forbidden:
            assert key not in body, f"Body should not have '{key}'"

    def test_all_slots_within_limits(self):
        """All generated text must fit within slots.json limits."""
        entries = [self._make_cover()] + [self._make_body(n) for n in range(2, 8)] + [self._make_cta()]
        for entry in entries:
            sanitized, warnings = enforce_slot_limits(entry, FAMILY_SLOTS)
            # No truncation should happen on well-formed fallback
            truncation_warnings = [w for w in warnings if "truncated" in w]
            assert truncation_warnings == [], f"Slide {entry['n']} ({entry['role']}): unexpected truncation: {truncation_warnings}"
