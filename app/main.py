"""ASGI entrypoint for uvicorn."""

from app.interface.http.main import create_app

app = create_app()
