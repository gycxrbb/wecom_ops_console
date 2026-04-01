from __future__ import annotations
from datetime import datetime, timedelta
from jinja2 import Environment, TemplateSyntaxError

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


def _looks_like_template(value: str) -> bool:
    return '{{' in value or '{%' in value or '{#' in value


def render_value(value, context: dict):
    if isinstance(value, str):
        if not _looks_like_template(value):
            return value
        try:
            return env.from_string(value).render(**context)
        except TemplateSyntaxError:
            return value
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    if isinstance(value, dict):
        return {k: render_value(v, context) for k, v in value.items()}
    return value
