"""JSON 提取工具的宽容解析测试。"""

from __future__ import annotations

import json

from super_ai.llm.json_output import extract_json_object


def test_extract_json_object_strict_json() -> None:
    payload = {"steps": [{"tool": "SearchLog"}], "sopDocumentIds": ["sop-1"]}
    text = json.dumps(payload, ensure_ascii=False)
    assert extract_json_object(text) == payload


def test_extract_json_object_accepts_markdown_code_fence() -> None:
    payload = {"steps": [{"tool": "SearchLog"}]}
    text = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    assert extract_json_object(text) == payload


def test_extract_json_object_accepts_surrounding_text() -> None:
    payload: dict[str, object] = {"steps": [], "sopDocumentIds": []}
    text = f"好的，计划如下：{json.dumps(payload, ensure_ascii=False)}，请查收。"
    assert extract_json_object(text) == payload


def test_extract_json_object_balances_braces_inside_strings() -> None:
    text = '前文 {"purpose": "包含 } 的字符串", "tool": "SearchLog"} 后文'
    assert extract_json_object(text) == {
        "purpose": "包含 } 的字符串",
        "tool": "SearchLog",
    }


def test_extract_json_object_rejects_garbage() -> None:
    assert extract_json_object("") is None
    assert extract_json_object("这不是 JSON") is None
    assert extract_json_object("[]") is None


def test_extract_json_object_picks_first_balanced_object() -> None:
    text = '{"a": 1} 之后还有 {"b": 2}'
    assert extract_json_object(text) == {"a": 1}
