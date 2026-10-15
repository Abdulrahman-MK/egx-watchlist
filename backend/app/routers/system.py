"""System Router.

Provides endpoints for:
- Health and market session status check (`GET /api/status`).
- Stream pause and resume toggles (`POST /api/system/pause`, `POST /api/system/resume`).
- Clean application shutdown (`POST /api/system/shutdown`).
"""

from fastapi import APIRouter
from app.market_guard import check_market_hours
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/status")
async def get_status():
    """Returns the market session status, stream state, and provider connectivity."""
    market_info = check_market_hours()
    return {
        "market": market_info,
        "provider": {
            "name": stream_manager.provider.name,
            "connected": stream_manager.provider.is_connected,
            "is_paused": stream_manager.is_paused,
        },
        "active_clients": len(stream_manager.active_connections),
    }


@router.post("/system/pause")
async def pause_stream():
    """Pauses real-time quote emissions without terminating the application."""
    result = await stream_manager.pause_stream()
    return {"success": True, **result}


@router.post("/system/resume")
async def resume_stream():
    """Resumes real-time quote emissions."""
    result = await stream_manager.resume_stream()
    return {"success": True, **result}


@router.post("/system/shutdown")
async def shutdown_system():
    """Gracefully closes market WebSockets, SQLite handles, and shuts down the process."""
    await stream_manager.shutdown_system()
    return {
        "success": True,
        "message": "System shutdown initiated. Server and connections closing.",
    }
