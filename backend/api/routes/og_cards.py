"""Open Graph image card generation for player social sharing."""

from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

# Card dimensions (Open Graph recommended 1200x630)
_CARD_W = 1200
_CARD_H = 630

# Colors (dark theme)
_BG_COLOR = (24, 24, 32)
_ACCENT_COLOR = (99, 179, 237)
_TEXT_COLOR = (230, 230, 240)
_MUTED_COLOR = (140, 140, 160)
_BRAND_COLOR = (99, 179, 237)

_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


def _render_player_card(summary: dict[str, Any]) -> bytes:
    """Render a player OG card as PNG using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (_CARD_W, _CARD_H), color=_BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Try to use a monospace/system font, fall back to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except (OSError, IOError):
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large
        font_brand = font_large

    name = summary.get("name", "Unknown Player")
    team = summary.get("team", "")
    pos = summary.get("pos", "")
    age = summary.get("age", "")
    player_type = summary.get("type", "")

    # Top accent bar
    draw.rectangle([(0, 0), (_CARD_W, 6)], fill=_ACCENT_COLOR)

    # Player name
    y = 60
    draw.text((60, y), name, fill=_TEXT_COLOR, font=font_large)
    y += 70

    # Team, Position, Age line
    meta_parts = []
    if team:
        meta_parts.append(team)
    if pos:
        meta_parts.append(pos)
    if age:
        meta_parts.append(f"Age {age}")
    meta_line = "  \u00B7  ".join(meta_parts)
    draw.text((60, y), meta_line, fill=_MUTED_COLOR, font=font_medium)
    y += 60

    # Separator line
    draw.line([(60, y), (_CARD_W - 60, y)], fill=(50, 50, 70), width=2)
    y += 30

    # Dynasty projections tagline
    draw.text((60, y), "20-Year Dynasty Projections", fill=_ACCENT_COLOR, font=font_medium)
    y += 50
    draw.text((60, y), "2026 \u2013 2045", fill=_MUTED_COLOR, font=font_small)
    y += 50

    # Player type indicator
    type_label = "Hitter" if player_type == "H" else "Pitcher" if player_type == "P" else ""
    if type_label:
        draw.text((60, y), type_label, fill=_MUTED_COLOR, font=font_small)

    # Brand footer
    footer_y = _CARD_H - 60
    draw.text((60, footer_y), "Fantasy Foundry", fill=_BRAND_COLOR, font=font_brand)
    draw.text((_CARD_W - 340, footer_y), "fantasy-foundry.com", fill=_MUTED_COLOR, font=font_brand)

    # Bottom accent bar
    draw.rectangle([(0, _CARD_H - 6), (_CARD_W, _CARD_H)], fill=_ACCENT_COLOR)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_default_card() -> bytes:
    """Render a generic FF OG card when no player summary is available."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (_CARD_W, _CARD_H), color=_BG_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except (OSError, IOError):
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_brand = font_large

    draw.rectangle([(0, 0), (_CARD_W, 6)], fill=_ACCENT_COLOR)
    draw.text((60, 200), "Fantasy Foundry", fill=_TEXT_COLOR, font=font_large)
    draw.text((60, 280), "20-Year Dynasty Baseball Projections", fill=_MUTED_COLOR, font=font_medium)
    draw.text((60, 340), "2026 \u2013 2045", fill=_ACCENT_COLOR, font=font_medium)
    draw.text((60, _CARD_H - 60), "fantasy-foundry.com", fill=_BRAND_COLOR, font=font_brand)
    draw.rectangle([(0, _CARD_H - 6), (_CARD_W, _CARD_H)], fill=_ACCENT_COLOR)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def build_og_cards_router(
    *,
    player_summary_index: dict[str, dict[str, Any]] | None = None,
) -> APIRouter:
    """Create OG image card routes."""
    router = APIRouter(tags=["og-cards"])

    @router.get("/api/og/player/{slug}.png")
    def get_player_og_card(slug: str):
        """Generate an Open Graph image card for a player."""
        clean_slug = slug.strip("/").split("/")[0] if slug else ""
        summary = (player_summary_index or {}).get(clean_slug)
        if summary:
            png_bytes = _render_player_card(summary)
        else:
            png_bytes = _render_default_card()
        return Response(content=png_bytes, media_type="image/png", headers=_CACHE_HEADERS)

    return router
