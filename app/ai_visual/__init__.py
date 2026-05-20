"""AI Visual Agent module — knowledge card generation for AI coach."""
from . import models  # noqa: F401  — register ORM tables
from .router import router

__all__ = ["router"]
