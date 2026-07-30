"""一次性数据生产脚本：fetch 远程提示词库(6 source)，用项目 AI 链路把每条归类到职业，
生成 profession_map.json 供前端 merge。NSFW 单独收集。跑完即删。

运行：在项目根 `python scripts/gen_profession_map.py`（用 .venv 的 python）。
输出：third_party/gpt_image_playground/src/lib/prompts/profession_map.json
  格式：{ "<prompt_id>": ["运营","管理层"], ..., "_nsfw": ["<id>", ...] }
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import httpx  # noqa: E402

from app.clients.ai_chat_client import chat_completion  # noqa: E402

REGISTRY_BASE = "https://raw.githubusercontent.com/yukkcat/image-prompts/main/dist/sources"
SOURCES = [
    "banana-prompt-quicker",
    "davidwu-gpt-image2-prompts",
    "awesome-gpt-image",
    "awesome-gpt4o-image-prompts",
    "youmind-gpt-image-2",
    "youmind-nano-banana-pro",
]
PROFESSIONS = ["健康教练", "运营", "开发", "管理层"]
BATCH = 20
OUT = os.path.join(
    PROJECT_ROOT, "third_party/gpt_image_playground/src/lib/prompts/profession_map.json"
)

SYSTEM = (
    "你是 AI 绘图提示词的职业分类助手。把每条提示词归类到它最可能服务的人群(可多选,都不沾边返回空数组):\n"
    "- 健康教练:食谱、营养、健身、健康科普、慢病、身体管理、饮食指导\n"
    "- 运营:海报、活动、营销、banner、促销、电商、封面、社群、卡片\n"
    "- 开发:流程图、信息图、架构图、UI、界面、原型、技术示意、思维导图\n"
    "- 管理层:PPT、汇报、商务、对外宣传、品牌、演讲、杂志排版\n"
    "同时判断是否含 NSFW(色情/裸露/血腥/暴力,企业场景必须剔除)。\n"
    "只返回严格 JSON 数组,不要任何解释文字。格式:[{\"id\":\"...\",\"professions\":[...],\"nsfw\":false}]"
)


def fetch_all() -> list[dict]:
    items: list[dict] = []
    with httpx.Client(timeout=60, trust_env=False) as c:
        for sid in SOURCES:
            for attempt in range(3):
                try:
                    r = c.get(f"{REGISTRY_BASE}/{sid}.json")
                    r.raise_for_status()
                    data = r.json()
                    for it in data:
                        it["sourceId"] = sid
                        items.append(it)
                    print(f"  fetched {sid}: {len(data)}")
                    break
                except Exception as exc:
                    print(f"  fetch {sid} attempt {attempt+1} failed: {exc}")
                    if attempt == 2:
                        print(f"  !! skip {sid}")
    return items


def _parse_json_array(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        # 去掉 ```json ... ``` 围栏
        inner = text.split("```")
        if len(inner) >= 2:
            text = inner[1]
            if text.startswith("json"):
                text = text[4:]
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def classify_batch(batch: list[dict]) -> list[dict]:
    payload = json.dumps(
        [
            {
                "id": it.get("id"),
                "title": (it.get("title") or "")[:60],
                "tags": (it.get("tags") or [])[:6],
                "prompt": (it.get("prompt") or "")[:200],
            }
            for it in batch
        ],
        ensure_ascii=False,
    )
    content, _ = await chat_completion(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.0,
        max_tokens=2048,
    )
    return _parse_json_array(content)


async def main() -> None:
    items = fetch_all()
    print(f"total fetched: {len(items)} prompts")
    if not items:
        print("no data, abort")
        return

    profession_map: dict[str, list[str]] = {}
    nsfw_ids: list[str] = []
    for i in range(0, len(items), BATCH):
        batch = items[i : i + BATCH]
        res: list[dict] = []
        for attempt in range(2):
            try:
                res = await classify_batch(batch)
                break
            except Exception as exc:
                print(f"  batch {i} attempt {attempt+1} failed: {exc}")
        if not res:
            print(f"  !! batch {i} skipped (will fall back to 通用)")
            continue
        for r in res:
            rid = r.get("id")
            if not rid:
                continue
            profs = [p for p in (r.get("professions") or []) if p in PROFESSIONS]
            profession_map[rid] = profs
            if r.get("nsfw"):
                nsfw_ids.append(rid)
        print(f"  {i + len(batch)}/{len(items)} done")

    profession_map["_nsfw"] = nsfw_ids
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(profession_map, f, ensure_ascii=False, indent=2)

    dist = Counter()
    for key, profs in profession_map.items():
        if key == "_nsfw":
            continue
        if not profs:
            dist["通用"] += 1
        else:
            for p in profs:
                dist[p] += 1
    print("profession distribution:", dict(dist))
    print(f"nsfw count: {len(nsfw_ids)}")
    print(f"written: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
