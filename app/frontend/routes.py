"""Routes for frontend debug UI."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
FRONTEND_DIR = Path(__file__).resolve().parent
STATIC_DIR = FRONTEND_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@router.get("/ui")
async def debug_ui() -> FileResponse:
    """Serve browser debug UI page."""

    return FileResponse(INDEX_FILE)
