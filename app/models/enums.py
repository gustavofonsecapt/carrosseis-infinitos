from __future__ import annotations

from enum import Enum


class ProjectType(str, Enum):
    CAROUSEL = "carousel"
    STORIES_10X = "stories_10x"


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    OUTLINED = "outlined"
    RENDERING = "rendering"
    RENDERED = "rendered"


class SlideRole(str, Enum):
    COVER = "cover"
    BODY = "body"
    CTA = "cta"
    FRAME = "frame"
    FRAME_CTA = "frame_cta"
