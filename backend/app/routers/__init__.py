"""Routers Package."""
from app.routers.system import router as system_router
from app.routers.symbols import router as symbols_router
from app.routers.watchlist import router as watchlist_router

__all__ = ["system_router", "symbols_router", "watchlist_router"]
