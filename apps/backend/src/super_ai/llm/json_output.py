"""LLM 输出的 JSON 提取工具（宽容解析，替代贪婪正则）。"""

from __future__ import annotations

import json
import re
from typing import cast


def extract_json_object(text: str) -> dict[str, object] | None:
    """从模型输出提取完整 JSON 对象。

    依次尝试：整体解析（严格 JSON-only）、`````json`` 代码块、括号配平提取。
    返回 None 表示未能提取到合法 JSON 对象。与贪婪 ``re.search(r"\\{.*\\}")``
    相比，括号配平在字符串内容包含 ``}`` 时不会提前截断。
    """
    if not text or not text.strip():
        return None
    parsed = _parse_json(text.strip())
    if parsed is not None:
        return parsed
    fenced = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, flags=re.DOTALL)
    if fenced is not None:
        parsed = _parse_json(fenced.group(1))
        if parsed is not None:
            return parsed
    return _extract_balanced(text)


def _parse_json(text: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return cast(dict[str, object], parsed)
    return None


def _extract_balanced(text: str) -> dict[str, object] | None:
    """从文本中括号配平提取第一个完整 JSON 对象（字符串感知）。"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return _parse_json(text[start : index + 1])
    return None
