"""企微 markdown 消息拆分工具 — 超过 4096 字节上限时自动拆为多条。"""
from __future__ import annotations

_WECOM_MARKDOWN_BYTE_LIMIT = 4096


def _byte_len(text: str) -> int:
    return len(text.encode('utf-8'))


def split_markdown_content(content: str, limit: int = _WECOM_MARKDOWN_BYTE_LIMIT) -> list[str]:
    """将超长 markdown 内容按段落拆分为多条，每条不超过 limit 字节。

    策略：
    1. 内容 <= limit → 原样返回 [content]
    2. 按 \\n\\n 分段，贪心合并段落到接近 limit
    3. 单个段落 > limit → 按行拆分该段落
    """
    if _byte_len(content) <= limit:
        return [content]

    paragraphs = content.split('\n\n')
    parts: list[str] = []
    current_lines: list[str] = []
    current_bytes = 0

    def _flush():
        nonlocal current_lines, current_bytes
        if current_lines:
            parts.append('\n\n'.join(current_lines))
            current_lines = []
            current_bytes = 0

    for para in paragraphs:
        para_bytes = _byte_len(para)

        # 单个段落超限 → 按行拆分
        if para_bytes > limit:
            _flush()
            _split_long_paragraph(para, limit, parts)
            continue

        # 加上这个段落后是否超限
        separator_bytes = 2 if current_lines else 0  # '\n\n' = 2 bytes
        if current_bytes + separator_bytes + para_bytes > limit:
            _flush()

        current_lines.append(para)
        current_bytes += (separator_bytes + para_bytes)

    _flush()
    return parts if parts else [content]


def _split_long_paragraph(para: str, limit: int, parts: list[str]) -> None:
    """按行拆分单个超长段落，每条不超过 limit 字节。"""
    lines = para.split('\n')
    chunk_lines: list[str] = []
    chunk_bytes = 0

    for line in lines:
        line_bytes = _byte_len(line)
        separator_bytes = 1 if chunk_lines else 0  # '\n' = 1 byte

        if chunk_bytes + separator_bytes + line_bytes > limit and chunk_lines:
            parts.append('\n'.join(chunk_lines))
            chunk_lines = []
            chunk_bytes = 0

        chunk_lines.append(line)
        chunk_bytes += (separator_bytes + line_bytes)

    if chunk_lines:
        parts.append('\n'.join(chunk_lines))
