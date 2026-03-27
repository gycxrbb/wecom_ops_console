from __future__ import annotations
from datetime import datetime, timedelta
from jinja2 import Environment

env = Environment(autoescape=False)

def default_context(now: datetime | None = None, **extra):
    now = now or datetime.now()
    ctx = {
        'today': now.strftime('%Y-%m-%d'),
        'tomorrow': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
        'weekday': now.strftime('%A'),
    }
    ctx.update(extra)
    return ctx


def render_value(value, context: dict):
    if isinstance(value, str):
        return env.from_string(value).render(**context)
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    if isinstance(value, dict):
        return {k: render_value(v, context) for k, v in value.items()}
    return value
