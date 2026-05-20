"""Diagnose AI visual image API connectivity and payload compatibility.

Default mode is low-cost: DNS/TCP/TLS plus /models checks. Use --generate to
send a real /images/generations request.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import ssl
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""
    elapsed_ms: int = 0


def _redact(value: str, *, keep: int = 4) -> str:
    if not value:
        return "<empty>"
    if len(value) <= keep * 2:
        return "***"
    return f"{value[:keep]}...{value[-keep:]}"


def _json_preview(data: object, limit: int = 900) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def _redact_image_payload(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cloned = dict(data)
    rows = cloned.get("data")
    if isinstance(rows, list):
        safe_rows = []
        for row in rows:
            if not isinstance(row, dict):
                safe_rows.append(row)
                continue
            safe_row = dict(row)
            if "b64_json" in safe_row:
                safe_row["b64_json"] = f"<redacted base64 chars={len(str(safe_row['b64_json']))}>"
            safe_rows.append(safe_row)
        cloned["data"] = safe_rows
    return cloned


def _response_preview(resp: httpx.Response, limit: int = 900) -> str:
    content_type = resp.headers.get("content-type", "")
    text = resp.text
    if "application/json" in content_type:
        try:
            return _json_preview(_redact_image_payload(resp.json()), limit=limit)
        except Exception:
            pass
    return text[:limit] + ("...<truncated>" if len(text) > limit else "")


def _exception_chain(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(f"{type(current).__module__}.{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)


def _timer() -> tuple[float, callable]:
    start = time.perf_counter()
    return start, lambda: int((time.perf_counter() - start) * 1000)


def _base_url() -> str:
    return settings.ai_base_url.rstrip("/")


def _host_port(base_url: str) -> tuple[str, int]:
    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise ValueError(f"Invalid ai_base_url: {base_url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname, port


def check_dns(host: str) -> CheckResult:
    start, elapsed = _timer()
    try:
        rows = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        addrs = sorted({row[4][0] for row in rows})
        return CheckResult("dns", "ok", ", ".join(addrs[:8]), elapsed())
    except Exception as exc:
        return CheckResult("dns", "error", _exception_chain(exc), elapsed())


def check_tcp(host: str, port: int, timeout: float) -> CheckResult:
    start, elapsed = _timer()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return CheckResult("tcp", "ok", f"{host}:{port}", elapsed())
    except Exception as exc:
        return CheckResult("tcp", "error", _exception_chain(exc), elapsed())


def check_tls(host: str, port: int, timeout: float) -> CheckResult:
    start, elapsed = _timer()
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls_sock:
                cert = tls_sock.getpeercert()
                subject = cert.get("subject", [])
                issuer = cert.get("issuer", [])
                detail = {
                    "version": tls_sock.version(),
                    "cipher": tls_sock.cipher()[0] if tls_sock.cipher() else None,
                    "notAfter": cert.get("notAfter"),
                    "subject": subject[:1],
                    "issuer": issuer[:1],
                }
                return CheckResult("tls", "ok", _json_preview(detail, limit=500), elapsed())
    except Exception as exc:
        return CheckResult("tls", "error", _exception_chain(exc), elapsed())


async def http_request(
    *,
    name: str,
    method: str,
    url: str,
    http2: bool,
    timeout: float,
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
    expected_http_error: bool = False,
) -> CheckResult:
    start, elapsed = _timer()
    try:
        async with httpx.AsyncClient(http2=http2, timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, json=json_body)
            detail = {
                "http_version": resp.http_version,
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type"),
                "body": _response_preview(resp),
            }
            status = "ok" if resp.status_code < 400 or expected_http_error else "http_error"
            return CheckResult(name, status, _json_preview(detail), elapsed())
    except Exception as exc:
        detail = _exception_chain(exc)
        if getattr(exc, "__traceback__", None):
            detail += "\n" + "".join(traceback.format_tb(exc.__traceback__)[-4:])
        return CheckResult(name, "error", detail, elapsed())


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }


def _model_name(args: argparse.Namespace) -> str:
    return args.model or settings.ai_visual_model


def _current_payload(args: argparse.Namespace) -> dict:
    return {
        "model": _model_name(args),
        "prompt": args.prompt,
        "n": 1,
        "size": args.size,
        "quality": "auto",
    }


def _compat_payload(args: argparse.Namespace) -> dict:
    return {
        "model": _model_name(args),
        "prompt": args.prompt,
        "n": 1,
        "size": args.size if args.size != "auto" else "1024x1024",
    }


def _invalid_image_probe_payload() -> dict:
    return {
        "model": "__diagnostic_invalid_model__",
        "prompt": "diagnostic endpoint probe only; expected to fail before generation",
        "n": 1,
        "size": "1024x1024",
    }


async def run(args: argparse.Namespace) -> int:
    base_url = _base_url()
    host, port = _host_port(base_url)
    timeout = args.timeout
    image_url = f"{base_url}/images/generations"
    models_url = f"{base_url}/models"

    print("== AI visual image API diagnostics ==")
    print(f"base_url: {base_url}")
    print(f"host: {host}:{port}")
    print(f"model: {_model_name(args)}")
    print(f"api_key: {_redact(settings.ai_api_key)}")
    print(f"http2_enabled(config): {settings.ai_http2_enabled}")
    print(f"generate: {args.generate}")
    print()

    results: list[CheckResult] = [
        check_dns(host),
        check_tcp(host, port, timeout),
    ]
    if urlparse(base_url).scheme == "https":
        results.append(check_tls(host, port, timeout))

    protocols = [True, False] if args.protocol == "both" else [args.protocol == "http2"]
    for http2 in protocols:
        suffix = "http2" if http2 else "http1"
        results.append(await http_request(
            name=f"models_{suffix}",
            method="GET",
            url=models_url,
            http2=http2,
            timeout=timeout,
            headers=_auth_headers(),
        ))

    if not args.skip_image_endpoint_probe:
        print("\n-- image endpoint probe --")
        print("Sending an intentionally invalid model to /images/generations; expected result is HTTP 4xx, not an image.")
        for http2 in protocols:
            suffix = "http2" if http2 else "http1"
            results.append(await http_request(
                name=f"image_endpoint_probe_{suffix}",
                method="POST",
                url=image_url,
                http2=http2,
                timeout=timeout,
                headers=_auth_headers(),
                json_body=_invalid_image_probe_payload(),
                expected_http_error=True,
            ))

    if args.generate:
        variants = ["current", "compat"] if args.payload == "both" else [args.payload]
        for variant in variants:
            payload = _current_payload(args) if variant == "current" else _compat_payload(args)
            print(f"\n-- generation payload ({variant}) --")
            print(_json_preview({**payload, "prompt": payload["prompt"][:120]}))
            for http2 in protocols:
                suffix = "http2" if http2 else "http1"
                results.append(await http_request(
                    name=f"generate_{variant}_{suffix}",
                    method="POST",
                    url=image_url,
                    http2=http2,
                    timeout=max(timeout, settings.ai_visual_generation_timeout_seconds),
                    headers=_auth_headers(),
                    json_body=payload,
                ))

    print("\n== results ==")
    has_error = False
    for result in results:
        if result.status in {"error", "http_error"}:
            has_error = True
        print(f"[{result.status.upper()}] {result.name} ({result.elapsed_ms}ms)")
        if result.detail:
            print(result.detail)
        print()

    print("== hints ==")
    print("- dns/tcp/tls error: local network, firewall, proxy, DNS, or certificate path issue.")
    print("- models_http2 error but models_http1 ok: HTTP/2 compatibility issue; set AI_HTTP2_ENABLED=false for this provider.")
    print("- /models ok but /images/generations disconnects: likely provider image endpoint/model/payload or upstream gateway issue.")
    print("- current payload fails but compat payload returns HTTP 4xx/ok: provider may not accept size=auto or quality=auto.")
    print("- HTTP 401/403: API key/account permission; HTTP 404: endpoint/base_url/model route; HTTP 429: quota/rate limit.")
    return 1 if has_error else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose AI visual image API connectivity.")
    parser.add_argument("--generate", action="store_true", help="Call /images/generations. This can consume image credits.")
    parser.add_argument("--protocol", choices=["both", "http2", "http1"], default="both")
    parser.add_argument("--payload", choices=["current", "compat", "both"], default="both")
    parser.add_argument("--skip-image-endpoint-probe", action="store_true", help="Skip invalid-model /images/generations probe.")
    parser.add_argument("--prompt", default="生成一张中文健康饮食建议卡片，主题：出差期间如何选择餐食。")
    parser.add_argument("--size", default="auto")
    parser.add_argument("--model", default="", help="Override AI visual model for diagnostics only.")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
