#!/usr/bin/env python3
"""Run the FastAPI server for the armor selection API."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "armor_select.backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Enable auto-reload during development
    )
