from __future__ import annotations

import re
from collections.abc import Callable
from html import escape as html_escape
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

_PLAYER_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,120}$")
_SITE_URL = "https://fantasy-foundry.com"


def build_player_summary_index(
    bat_data: list[dict[str, Any]], pit_data: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Build a slug→{name, team, pos, age, type} index from projection data.

    Uses the first (most recent) row per player entity key. Hitter data takes
    priority over pitcher data for players appearing in both.
    """
    index: dict[str, dict[str, Any]] = {}
    # Pitchers first; hitters override for two-way players
    for row in pit_data:
        key = str(row.get("PlayerEntityKey", "")).strip()
        if not key or key in index:
            continue
        index[key] = {
            "name": row.get("Player", ""),
            "team": row.get("Team", ""),
            "pos": row.get("Pos", ""),
            "age": row.get("Age"),
            "type": "P",
        }
    for row in bat_data:
        key = str(row.get("PlayerEntityKey", "")).strip()
        if not key:
            continue
        if key in index and index[key]["type"] == "H":
            continue
        index[key] = {
            "name": row.get("Player", ""),
            "team": row.get("Team", ""),
            "pos": row.get("Pos", ""),
            "age": row.get("Age"),
            "type": "H",
        }
    return index


def build_frontend_assets_router(
    *,
    index_path: Path,
    assets_root: Path,
    app_build_id: str,
    index_build_token: str,
    player_keys_getter: Callable[[], list[str]] | None = None,
    player_summary_index: dict[str, dict[str, Any]] | None = None,
) -> APIRouter:
    """Create frontend index/static asset routes for built Vite output."""
    index_cache_headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-App-Build": app_build_id,
    }
    asset_cache_headers = {"Cache-Control": "public, max-age=31536000, immutable"}
    router = APIRouter(tags=["frontend"])

    def _read_index_html() -> str:
        try:
            html = index_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="Frontend dist/index.html is unavailable. Build the frontend with: npm run build (in frontend/).",
            ) from exc
        if index_build_token in html:
            html = html.replace(index_build_token, app_build_id)
        return html

    @router.get("/")
    def serve_index():
        return HTMLResponse(content=_read_index_html(), headers=index_cache_headers)

    @router.get("/player/{slug:path}")
    def serve_player_page(slug: str):
        """SPA fallback for player profile pages with SEO-friendly meta tags."""
        html = _read_index_html()
        clean_slug = slug.strip("/").split("/")[0] if slug else ""
        summary = (player_summary_index or {}).get(clean_slug)
        if summary:
            display_name = html_escape(summary["name"])
            team = html_escape(summary["team"])
            pos = html_escape(summary["pos"])
            age = summary.get("age")
            label = f"{display_name} ({team}, {pos})"
            title = f"{label} Dynasty Projections 2026-2045 | Fantasy Foundry"
            age_part = f", age {age}" if age else ""
            desc = (
                f"20-year dynasty projections for {display_name} ({team}, {pos}{age_part}). "
                f"Year-by-year stats, dynasty value trajectory, and career totals."
            )
        else:
            display_name = clean_slug.replace("-", " ").title() if clean_slug else "Player"
            title = f"{display_name} Dynasty Value & Projections | Fantasy Foundry"
            desc = f"20-year dynasty projections and value analysis for {display_name}. Browse year-by-year stats from 2026 through 2045."
        canonical = f"{_SITE_URL}/player/{clean_slug}"
        html = html.replace(
            "<title>Fantasy Foundry | 20-Year Dynasty Baseball Projections</title>",
            f"<title>{title}</title>",
        )
        html = html.replace(
            'content="Browse 2026-2045 MLB dynasty projections, configure league settings, and generate custom dynasty rankings in minutes."',
            f'content="{desc}"',
        )
        html = html.replace(
            f'content="{_SITE_URL}/"',
            f'content="{canonical}"',
        )
        html = html.replace(
            f'href="{_SITE_URL}/"',
            f'href="{canonical}"',
        )
        html = html.replace(
            'content="Fantasy Foundry | 20-Year Dynasty Baseball Projections"',
            f'content="{title}"',
        )
        og_image_url = f"{_SITE_URL}/api/og/player/{clean_slug}.png"
        html = html.replace(
            f'content="{_SITE_URL}/assets/og-image.png"',
            f'content="{og_image_url}"',
        )
        og_alt = f"{display_name} Dynasty Projections | Fantasy Foundry"
        html = html.replace(
            'content="Fantasy Foundry \u2014 20-Year Dynasty Baseball Projections"',
            f'content="{og_alt}"',
        )
        return HTMLResponse(content=html, headers=index_cache_headers)

    @router.get("/movers")
    def serve_movers_page():
        """SPA fallback for the movers/risers-fallers page with SEO meta tags."""
        html = _read_index_html()
        title = "This Week's Biggest Movers — Dynasty Projection Changes | Fantasy Foundry"
        desc = "See which dynasty players are rising and falling this week. Updated projections, biggest gainers and losers across 20-year dynasty valuations."
        canonical = f"{_SITE_URL}/movers"
        html = html.replace(
            "<title>Fantasy Foundry | 20-Year Dynasty Baseball Projections</title>",
            f"<title>{title}</title>",
        )
        html = html.replace(
            'content="Browse 2026-2045 MLB dynasty projections, configure league settings, and generate custom dynasty rankings in minutes."',
            f'content="{desc}"',
        )
        html = html.replace(
            f'content="{_SITE_URL}/"',
            f'content="{canonical}"',
        )
        html = html.replace(
            f'href="{_SITE_URL}/"',
            f'href="{canonical}"',
        )
        html = html.replace(
            'content="Fantasy Foundry | 20-Year Dynasty Baseball Projections"',
            f'content="{title}"',
        )
        return HTMLResponse(content=html, headers=index_cache_headers)

    @router.get("/sitemap.xml")
    def serve_sitemap():
        """Generate sitemap from known player keys."""
        urls = [
            f'  <url><loc>{_SITE_URL}/</loc><priority>1.0</priority></url>',
            f'  <url><loc>{_SITE_URL}/movers</loc><priority>0.8</priority></url>',
        ]
        if player_keys_getter:
            for key in player_keys_getter():
                safe_key = str(key).strip()
                if safe_key and _PLAYER_SLUG_RE.match(safe_key):
                    urls.append(f'  <url><loc>{_SITE_URL}/player/{safe_key}</loc></url>')
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls)
            + "\n</urlset>\n"
        )
        return Response(content=xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})

    @router.get("/assets/{asset_path:path}")
    def serve_frontend_asset(asset_path: str):
        normalized = asset_path.lstrip("/")
        candidate = (assets_root / normalized).resolve()
        root = assets_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Asset not found")
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")
        return FileResponse(path=str(candidate), headers=asset_cache_headers)

    return router
