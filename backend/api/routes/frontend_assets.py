from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse


def build_frontend_assets_router(
    *,
    index_path: Path,
    assets_root: Path,
    app_build_id: str,
    index_build_token: str,
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

    @router.get("/")
    def serve_index():
        try:
            html = index_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="Frontend dist/index.html is unavailable. Build the frontend with: npm run build (in frontend/).",
            ) from exc

        if index_build_token in html:
            html = html.replace(index_build_token, app_build_id)

        return HTMLResponse(content=html, headers=index_cache_headers)

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
