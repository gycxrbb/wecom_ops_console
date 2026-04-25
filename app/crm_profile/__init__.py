"""CRM Customer 360 Profile sub-package.

Only exposes ``router`` and ``init_models()`` to the parent app.
"""
from .router import router

__all__ = ["router"]


def init_models() -> None:
    """Register CRM AI audit ORM models so Base.metadata.create_all picks them up."""
    from . import models as _models  # noqa: F401
