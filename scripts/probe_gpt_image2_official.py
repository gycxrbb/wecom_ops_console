"""Reproduce gpt-image-2 generation using the official OpenAI Python SDK.

目的：用官方 SDK + 长 timeout 直连 aihubmix，验证 60s 断连到底是否出自我们的
httpx 客户端配置。和 image_client.py 的 httpx 实现完全独立，且尽量贴近 aihubmix
官方 sample。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\probe_gpt_image2_official.py
    # 也可指定模型 / size：
    .\\.venv\\Scripts\\python.exe scripts\\probe_gpt_image2_official.py --model gpt-image-2 --size 1024x1024

判断标准：
- 跑过 60s 拿到图 → 我们代码无问题，aihubmix 这路链路在你机器上是通的，问题只剩
  "为什么 image_client.py 之前在 60s 就断"——需要去看 httpx debug 日志。
- 同样 ~60s 断开 → 出站网络（Aliyun NAT / 公司防火墙 / ISP）在 60s 处掐 TCP，
  和我们代码无关；要么改走支持长 idle 的链路，要么联系网络方调超时。
- 报错且 aihubmix 后台仍计费 → aihubmix 网关问题，开工单。
"""
from __future__ import annotations

import argparse
import base64
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=settings.ai_visual_model)
    parser.add_argument("--size", default="1024x1024", help="auto | 1024x1024 | 1024x1536 | 1536x1024")
    parser.add_argument("--quality", default="auto", help="auto | high | medium | low")
    parser.add_argument(
        "--prompt",
        default="A red apple on a wooden table, photorealistic, soft natural light.",
        help="Short prompt to minimize generation time.",
    )
    parser.add_argument("--timeout", type=float, default=900.0, help="Client timeout seconds (default 900 = 15 min).")
    parser.add_argument("--out", default="data/probe_gpt_image2.png")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: `openai` SDK not installed in this venv. Run: pip install openai", file=sys.stderr)
        return 2

    if not settings.ai_api_key:
        print("ERROR: settings.ai_api_key is empty (.env AI_API_KEY missing).", file=sys.stderr)
        return 2

    base_url = settings.ai_base_url
    print("== gpt-image-2 official SDK probe ==")
    print(f"base_url   : {base_url}")
    print(f"model      : {args.model}")
    print(f"size       : {args.size}")
    print(f"quality    : {args.quality}")
    print(f"timeout    : {args.timeout}s")
    print(f"prompt_len : {len(args.prompt)} chars")
    print()

    client = OpenAI(
        api_key=settings.ai_api_key,
        base_url=base_url,
        timeout=args.timeout,
        max_retries=0,  # 关掉重试，看清单次真实耗时
    )

    started = time.perf_counter()
    try:
        response = client.images.generate(
            model=args.model,
            prompt=args.prompt,
            n=1,
            size=args.size,
            quality=args.quality,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"[FAIL] elapsed={elapsed:.1f}s")
        print(f"exception_type: {type(exc).__module__}.{type(exc).__name__}")
        print(f"exception_msg : {exc}")
        cause = exc.__cause__ or exc.__context__
        if cause is not None:
            print(f"caused_by     : {type(cause).__module__}.{type(cause).__name__}: {cause}")
        print()
        print("traceback (last 10 frames):")
        traceback.print_exc(limit=10)
        print()
        print("---- 判断 ----")
        if elapsed < 90:
            print(f"≈ {elapsed:.0f}s 被断开 → 不是 aihubmix 网关，多半是你→aihubmix 之间")
            print("  的出站网络（Aliyun NAT、公司防火墙、ISP）TCP idle timeout 60s 在掐连接。")
            print("  在 image_client.py 里调任何 httpx 超时都救不了——需要走 idle 容忍更长的链路。")
        else:
            print(f"{elapsed:.0f}s 才断开 → aihubmix 真实生成链路问题，开工单给他们。")
        return 1

    elapsed = time.perf_counter() - started
    print(f"[OK] elapsed={elapsed:.1f}s")

    img = response.data[0]
    if getattr(img, "b64_json", None):
        out_path = ROOT / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(img.b64_json))
        print(f"saved: {out_path}")
        print(f"b64_len: {len(img.b64_json)}")
    elif getattr(img, "url", None):
        print(f"image_url: {img.url}")
    else:
        print(f"unexpected response shape: {response}")

    print()
    print("---- 判断 ----")
    print(f"官方 SDK 在 {elapsed:.0f}s 内拿到图 → 链路本身是通的。")
    print("如果我们后端 image_client.py 仍报 60s 断开，需要进一步排查 httpx 的 trust_env、")
    print("代理、TLS 行为差异；可以打开 HTTPX_LOG_LEVEL=DEBUG 跑一次对比。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
