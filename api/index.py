"""Vercel Python function entrypoint; also used by uvicorn locally."""
from src.feedback_prd.web_api import app

__all__ = ["app"]
