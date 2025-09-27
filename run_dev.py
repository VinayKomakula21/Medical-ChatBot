#!/usr/bin/env python3
"""
Development server runner for Medical ChatBot.
This replaces the old main.py and provides a cleaner entry point.
"""

import uvicorn
from app.core.config import settings


def main():
    """Run the development server."""
    print(f"🚀 Starting Medical ChatBot API...")
    print(f"📍 Server: http://localhost:{settings.PORT}")
    print(f"📚 API Docs: http://localhost:{settings.PORT}/api/v1/docs")
    print(f"📊 ReDoc: http://localhost:{settings.PORT}/api/v1/redoc")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()