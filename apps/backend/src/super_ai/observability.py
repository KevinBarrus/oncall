"""Secret-safe structured logging and request correlation helpers."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar, Token
from threading import Lock
from time import monotonic
from typing import cast

_request_id: ContextVar[str | None] = ContextVar("super_ai_request_id", default=None)
_STRUCTURED_HANDLER_NAME = "super_ai_structured_events"
_SENSITIVE_KEYS = {
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "key",
    "password",
    "secret",
    "secret_id",
    "secret_key",
    "secretid",
    "secretkey",
    "token",
}


def set_request_id(request_id: str) -> Token[str | None]:
    """Set the active request correlation id for the current async context."""
    return _request_id.set(request_id)


def configure_structured_logging() -> None:
    """Ensure local runtime emits structured events through its own logger namespace."""
    logger = logging.getLogger("super_ai")
    logger.disabled = False
    logger.setLevel(logging.INFO)
    for name, configured_logger in logger.manager.loggerDict.items():
        if name.startswith("super_ai.") and isinstance(configured_logger, logging.Logger):
            configured_logger.disabled = False
    if any(handler.get_name() == _STRUCTURED_HANDLER_NAME for handler in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.set_name(_STRUCTURED_HANDLER_NAME)
    handler.setLevel(logging.INFO)
    handler.setFormatter(SanitizingFormatter("%(message)s"))
    logger.addHandler(handler)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request correlation context."""
    _request_id.reset(token)


def emit_event(logger: logging.Logger, event: str, **fields: object) -> None:
    """Emit one compact JSON event without raw request or provider payloads."""
    payload: dict[str, object] = {"event": event}
    request_id = _request_id.get()
    if request_id is not None:
        payload["requestId"] = request_id
    payload.update(fields)
    encoded = json.dumps(
        _redact(payload),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    logger.info(encoded)


def elapsed_ms(started_at: float) -> float:
    """Return an elapsed duration suitable for a structured event."""
    return round((monotonic() - started_at) * 1000, 3)


_business_metrics: dict[str, tuple[float, int]] = {}
_business_lock = Lock()


def record_business_metric(name: str, amount: float = 1.0) -> None:
    """Accumulate a business metric (total + sample count) for the /metrics endpoint.

    事件计数（如 chat 请求数）调用默认 ``amount=1``；可观测值（如上下文 token、
    MCP 延迟）调用时传数值，端点按 ``total / count`` 给出平均值。
    """
    with _business_lock:
        total, samples = _business_metrics.get(name, (0.0, 0))
        _business_metrics[name] = (total + amount, samples + 1)


def snapshot_business_metrics() -> dict[str, dict[str, object]]:
    """Snapshot accumulated business metrics with count, total, and average."""
    with _business_lock:
        return {
            name: {
                "count": samples,
                "total": round(total, 2),
                "average": round(total / samples, 2) if samples else 0.0,
            }
            for name, (total, samples) in sorted(_business_metrics.items())
        }


def reset_business_metrics() -> None:
    """Clear accumulated business metrics (test isolation helper)."""
    with _business_lock:
        _business_metrics.clear()


def _redact(value: object, *, parent_key: str | None = None) -> object:
    if parent_key is not None and _is_sensitive_key(parent_key):
        return "[redacted]"
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _redact(item, parent_key=str(key)) for key, item in mapping.items()}
    if isinstance(value, list):
        return [_redact(item, parent_key=parent_key) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return [_redact(item, parent_key=parent_key) for item in cast(tuple[object, ...], value)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("_key", "_password", "_secret", "_token")
    )


_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?P<quote_open>[\"']?)"
    r"(?P<key>[A-Za-z0-9_.-]*?"
    r"(?i:api[_-]?key|key|secret|password|passwd|credential|authorization|token|"
    r"(?:access|auth|refresh|bearer|id)[_-]?token|"
    r"[a-z0-9]+[_-]?(?:key|secret|password|token))"
    r")\s*[\"']?\s*(?P<sep>[:=])\s*"
    r"(?P<quote>[\"']?)(?P<value>[^\"'\s,;}]*)(?P=quote)"
)


class SanitizingFormatter(logging.Formatter):
    """Redact sensitive key-value pairs inside formatted log messages.

    对渲染后的 message（含 ``args`` 展开值）做文本脱敏，避免
    ``logger.error("config: %s", config)`` 之类的非结构化调用泄漏密钥。
    """

    def format(self, record: logging.LogRecord) -> str:
        rendered = record.getMessage()
        record.msg = _redact_text(rendered)
        record.args = ()
        # 对 super().format 的完整结果（含 exc_info 堆栈与 stack_info）再做一次
        # 文本脱敏，避免未来 logger.exception / exc_info=True 的堆栈泄漏敏感值
        return _redact_text(super().format(record))


def _redact_text(text: str) -> str:
    """Replace sensitive ``key: value`` / ``key=value`` pairs with a redacted value."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group("key")
        sep = match.group("sep")
        quote = match.group("quote")
        return f"{match.group('quote_open')}{key}{sep}{quote}***{quote}"

    return _SENSITIVE_VALUE_PATTERN.sub(_replace, text)
