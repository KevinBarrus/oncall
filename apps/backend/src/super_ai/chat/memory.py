"""Session-scoped chat context measurement and compression."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal, cast

from langchain_core.messages.utils import count_tokens_approximately

from super_ai.llm import LlmProvider
from super_ai.llm.json_output import extract_json_object
from super_ai.memory.repositories import (
    ChatMessageRecord,
    ChatSessionRecord,
    JsonDict,
    MemoryRepositories,
)
from super_ai.observability import emit_event, record_business_metric

logger = logging.getLogger(__name__)

ChatMemoryMode = Literal["every_30_turns", "context_70_percent", "manual"]
SUPPORTED_CHAT_MEMORY_MODES: tuple[ChatMemoryMode, ...] = (
    "every_30_turns",
    "context_70_percent",
    "manual",
)
AUTO_CONTEXT_THRESHOLD_PERCENT = 70.0
HARD_CONTEXT_THRESHOLD_PERCENT = 95.0
MEMORY_COMPACTION_INPUT_RATIO = 0.25
MEMORY_COMPACTION_MIN_TOKENS = 128
MEMORY_COMPACTION_MESSAGE_CAP_CHARS = 4_000
RUNTIME_OUTPUT_RESERVE_TOKENS = 2_048
RUNTIME_SAFETY_MARGIN_PERCENT = 90.0
MEMORY_SCHEMA_VERSION = 1
MEMORY_CATEGORIES = frozenset({"goal", "fact", "decision", "todo", "source", "recent_context"})
MEMORY_COMPACTION_TIMEOUT_SECONDS = 10
_MEMORY_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
MemoryCompactionScheduler = Callable[[str, str], Awaitable[None]]


class ChatContextLimitReached(RuntimeError):
    """Raised before persistence when a candidate message exceeds the hard budget."""


class ChatRuntimeContextLimitReached(RuntimeError):
    """Raised when an Agent run exhausts its input/tool/output budget."""


class MemoryFidelityError(RuntimeError):
    """Raised when a compacted memory cannot be traced to the source transcript."""


@dataclass(slots=True)
class ChatRuntimeContextBudget:
    """Track the approximate budget consumed by one LangChain Agent run."""

    context_window_tokens: int
    used_tokens: int
    input_limit_tokens: int
    llm_provider: LlmProvider | None

    @classmethod
    def create(
        cls,
        *,
        system_prompt: str,
        memory_summary: str | None,
        messages: list[ChatMessageRecord],
        context_window_tokens: int,
        llm_provider: LlmProvider | None = None,
    ) -> ChatRuntimeContextBudget:
        input_limit = (
            int(context_window_tokens * RUNTIME_SAFETY_MARGIN_PERCENT / 100)
            - RUNTIME_OUTPUT_RESERVE_TOKENS
        )
        return cls(
            context_window_tokens=context_window_tokens,
            used_tokens=estimate_context_tokens(
                system_prompt=system_prompt,
                memory_summary=memory_summary,
                messages=messages,
                llm_provider=llm_provider,
            ),
            input_limit_tokens=max(1, input_limit),
            llm_provider=llm_provider,
        )

    def add(self, value: object, *, role: str) -> None:
        value_tokens = count_tokens(_runtime_text(value), llm_provider=self.llm_provider)
        if self.used_tokens + value_tokens > self.input_limit_tokens:
            raise ChatRuntimeContextLimitReached
        self.used_tokens += value_tokens


@dataclass(frozen=True, slots=True)
class PreparedChatContext:
    session: ChatSessionRecord
    messages: tuple[ChatMessageRecord, ...]
    system_prompt: str


class ChatMemoryService:
    """Apply a session memory policy without deleting persisted history."""

    def __init__(
        self,
        *,
        repositories: MemoryRepositories,
        llm_provider: LlmProvider,
        context_window_tokens: int,
        schedule_compaction: MemoryCompactionScheduler | None = None,
    ) -> None:
        if context_window_tokens <= 0:
            raise ValueError("context_window_tokens must be positive")
        self._repositories = repositories
        self._llm_provider = llm_provider
        self._schedule_compaction = schedule_compaction
        self.context_window_tokens = context_window_tokens

    async def prepare_message(
        self,
        *,
        owner_user_id: str,
        session: ChatSessionRecord,
        history: list[ChatMessageRecord],
        system_prompt: str,
        content: str,
    ) -> PreparedChatContext:
        current = session
        # 归档后 active 历史即未压缩消息，无需按压缩边界切片
        uncompressed = history
        candidate = _candidate_user_message(current, owner_user_id, content)
        candidate_messages = [*uncompressed, candidate]
        candidate_tokens = estimate_context_tokens(
            system_prompt=system_prompt,
            memory_summary=current.memory_summary,
            messages=candidate_messages,
            llm_provider=self._llm_provider,
        )
        completed_turns = sum(message.role == "assistant" for message in uncompressed)
        should_compact = (current.memory_mode == "every_30_turns" and completed_turns >= 30) or (
            current.memory_mode == "context_70_percent"
            and _usage_percent(candidate_tokens, self.context_window_tokens)
            >= AUTO_CONTEXT_THRESHOLD_PERCENT
        )
        if should_compact and uncompressed and candidate_tokens < self._hard_limit_tokens:
            await self._schedule_automatic_compaction(owner_user_id, current.id)

        if candidate_tokens >= self._hard_limit_tokens and uncompressed:
            try:
                current = await self.compact_once(
                    owner_user_id=owner_user_id,
                    session=current,
                    history=history,
                    system_prompt=system_prompt,
                    timeout_seconds=MEMORY_COMPACTION_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                await self._repositories.chat.update_memory_state(
                    owner_user_id=owner_user_id,
                    session_id=current.id,
                    last_compaction_error=exc.__class__.__name__,
                    last_compaction_failed_at=datetime.now(timezone.utc),
                )
                record_business_metric("chat_compaction_failures")
                emit_event(
                    logger,
                    "chat.memory.compaction_failed",
                    sessionId=current.id,
                    errorCategory=exc.__class__.__name__,
                )
            else:
                uncompressed = await self._repositories.chat.list_active_messages(
                    owner_user_id=owner_user_id,
                    session_id=current.id,
                )
                candidate_messages = [*uncompressed, candidate]
                candidate_tokens = estimate_context_tokens(
                    system_prompt=system_prompt,
                    memory_summary=current.memory_summary,
                    messages=candidate_messages,
                    llm_provider=self._llm_provider,
                )

        if (
            _usage_percent(candidate_tokens, self.context_window_tokens)
            >= HARD_CONTEXT_THRESHOLD_PERCENT
        ):
            raise ChatContextLimitReached

        updated = await self._repositories.chat.update_memory_state(
            owner_user_id=owner_user_id,
            session_id=current.id,
            context_tokens=candidate_tokens,
        )
        record_business_metric("chat_context_tokens", float(candidate_tokens))
        return PreparedChatContext(
            session=updated or current,
            messages=tuple(candidate_messages),
            system_prompt=_prompt_with_memory(system_prompt, current.memory_summary),
        )

    @property
    def _hard_limit_tokens(self) -> float:
        return self.context_window_tokens * HARD_CONTEXT_THRESHOLD_PERCENT / 100

    async def _schedule_automatic_compaction(self, owner_user_id: str, session_id: str) -> None:
        if self._schedule_compaction is None:
            return
        try:
            await self._schedule_compaction(owner_user_id, session_id)
        except Exception as exc:
            emit_event(
                logger,
                "chat.memory.compaction_schedule_failed",
                sessionId=session_id,
                errorCategory=exc.__class__.__name__,
            )

    async def compact_once(
        self,
        *,
        owner_user_id: str,
        session: ChatSessionRecord,
        history: list[ChatMessageRecord],
        system_prompt: str,
        timeout_seconds: float | None = None,
    ) -> ChatSessionRecord:
        uncompressed = history
        compactable = _select_messages_for_compaction(
            messages=uncompressed,
            system_prompt=system_prompt,
            memory_summary=session.memory_summary,
            context_window_tokens=self.context_window_tokens,
            llm_provider=self._llm_provider,
        )
        if not compactable:
            return session
        operation = self._compact_messages(
            owner_user_id=owner_user_id,
            session=session,
            messages=compactable,
            system_prompt=system_prompt,
        )
        if timeout_seconds is None:
            return await operation
        return await asyncio.wait_for(operation, timeout=timeout_seconds)

    async def refresh_usage(
        self,
        *,
        owner_user_id: str,
        session: ChatSessionRecord,
        history: list[ChatMessageRecord],
        system_prompt: str,
    ) -> ChatSessionRecord:
        tokens = estimate_context_tokens(
            system_prompt=system_prompt,
            memory_summary=session.memory_summary,
            messages=history,
            llm_provider=self._llm_provider,
        )
        updated = await self._repositories.chat.update_memory_state(
            owner_user_id=owner_user_id,
            session_id=session.id,
            context_tokens=tokens,
        )
        return updated or session

    async def set_mode(
        self,
        *,
        owner_user_id: str,
        session: ChatSessionRecord,
        mode: ChatMemoryMode,
        history: list[ChatMessageRecord],
        system_prompt: str,
    ) -> ChatSessionRecord:
        updated = await self._repositories.chat.update_memory_state(
            owner_user_id=owner_user_id,
            session_id=session.id,
            memory_mode=mode,
        )
        current = updated or session
        return await self.refresh_usage(
            owner_user_id=owner_user_id,
            session=current,
            history=history,
            system_prompt=system_prompt,
        )

    async def _compact_messages(
        self,
        *,
        owner_user_id: str,
        session: ChatSessionRecord,
        messages: list[ChatMessageRecord],
        system_prompt: str,
    ) -> ChatSessionRecord:
        transcript = "\n".join(
            f"[message_id={message.id}] {message.role}: {message.content}" for message in messages
        )
        existing_memory = _memory_document(session.memory_summary)
        prompt = (
            "请将以下对话压缩为结构化中文记忆。只输出一个纯 JSON 对象，不要 Markdown "
            "代码围栏或任何额外文字。"
            'JSON 格式必须是：{"version":1,"summary":"...","items":['
            '{"category":"goal|fact|decision|todo|source|recent_context",'
            '"content":"...","sourceMessageIds":["消息 ID"]}]}。'
            "summary 不超过 1200 个汉字；每个 item 必须保留来源消息 ID；删除寒暄与重复内容。\n\n"
            f"已有记忆：\n{json.dumps(existing_memory, ensure_ascii=False)}\n\n"
            f"新增对话：\n{transcript}"
        )
        response = await self._llm_provider.create_chat_model().ainvoke(prompt)
        summary_text = _extract_model_text(response).strip()
        memory = _validated_memory_document(
            summary_text,
            allowed_source_ids={
                *{message.id for message in messages},
                *_memory_source_ids(existing_memory),
            },
        )
        if memory is None:
            raise RuntimeError("The model returned an invalid structured memory.")
        source_text = _compaction_source_text(transcript, existing_memory)
        if not _validate_memory_fidelity(memory, source_text=source_text):
            raise MemoryFidelityError(
                "The model returned memory claims that cannot be traced to the source."
            )
        summary = json.dumps(memory, ensure_ascii=False, separators=(",", ":"))
        tokens = estimate_context_tokens(
            system_prompt=system_prompt,
            memory_summary=summary,
            messages=[],
            llm_provider=self._llm_provider,
        )
        updated = await self._repositories.chat.archive_compacted_messages(
            owner_user_id=owner_user_id,
            session_id=session.id,
            memory_summary=summary,
            context_tokens=tokens,
            last_compacted_at=datetime.now(timezone.utc),
            message_ids=[message.id for message in messages],
            clear_compaction_error=True,
        )
        record_business_metric("chat_compactions")
        return updated or session


# ---------------------------------------------------------------------------
# tool output compression
# ---------------------------------------------------------------------------

TOOL_OUTPUT_COMPRESS_THRESHOLD_TOKENS = 2000
TOOL_OUTPUT_COMPRESS_INPUT_CAP_CHARS = 12_000
TOOL_OUTPUT_SIGNAL_PATTERN = re.compile(
    r"\b(error|fatal|critical|exception|traceback|deadlock|oom|killed|timeout|"
    r"corrupt(?:ed|ion)?|retry|degraded|fallback|rejected|exhausted|overflow)\b",
    flags=re.IGNORECASE,
)


async def maybe_compress_tool_output(
    text: str,
    *,
    tool_name: str,
    llm_provider: LlmProvider,
    threshold_tokens: int = TOOL_OUTPUT_COMPRESS_THRESHOLD_TOKENS,
) -> str:
    """Compress a tool output via LLM summarisation when it exceeds the threshold.

    Token count prefers the configured model's tokenizer, falling back to a
    safe Unicode estimate.  If the output is below the threshold it is
    returned unchanged.  Otherwise the LLM is asked to produce a concise
    summary preserving all key facts.
    """
    token_count = count_tokens(text, llm_provider=llm_provider)
    if token_count <= threshold_tokens:
        return text

    capped = _select_text_for_compression(text, max_chars=TOOL_OUTPUT_COMPRESS_INPUT_CAP_CHARS)
    prompt = (
        "你是一个工具输出压缩器。请将以下工具输出压缩为简洁摘要，保留所有关键事实、"
        "数字、名称、状态、错误信息和可操作信息。删除冗余描述和格式化噪音。"
        "只输出压缩后的摘要，不要加任何前言。\n\n"
        f"工具名称：{tool_name}\n"
        f"原始输出：\n{capped}"
    )
    try:
        response = await llm_provider.create_chat_model().ainvoke(prompt)
        summary = _extract_model_text(response).strip()
        if summary:
            return f"[compressed] {summary}"
        failure_category = "EmptySummary"
    except Exception as exc:
        failure_category = exc.__class__.__name__

    emit_event(
        logger,
        "chat.tool_compression.fallback",
        toolName=tool_name,
        compressionMode="sampled_fallback",
        failureCategory=failure_category,
    )
    record_business_metric("tool_compression_fallbacks")

    return f"{capped[:4000]}\n\n[... 输出已按信号、首尾和时间线采样，原文约 {token_count} tokens]"


async def maybe_compress_structured_tool_output(
    value: Mapping[str, object],
    *,
    tool_name: str,
    llm_provider: LlmProvider,
    threshold_tokens: int = TOOL_OUTPUT_COMPRESS_THRESHOLD_TOKENS,
) -> dict[str, object] | Mapping[str, object]:
    """Compress a large mapping without discarding its machine-readable envelope."""
    encoded = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if count_tokens(encoded, llm_provider=llm_provider) <= threshold_tokens:
        return value
    compressed = await maybe_compress_tool_output(
        encoded,
        tool_name=tool_name,
        llm_provider=llm_provider,
        threshold_tokens=threshold_tokens,
    )
    mode = "llm_summary" if compressed.startswith("[compressed]") else "sampled_fallback"
    metadata = tool_output_compression_metadata(encoded, compressed, mode=mode)
    if mode == "sampled_fallback":
        metadata["compressionFailed"] = True
    return {
        "content": compressed.removeprefix("[compressed] "),
        "preserved": _preserve_structured_fields(value),
        "_compression": metadata,
    }


def tool_output_compression_metadata(
    original: str,
    compressed: str,
    *,
    mode: str,
) -> dict[str, object]:
    return {
        "mode": mode,
        "sourceHash": sha256(original.encode("utf-8")).hexdigest(),
        "originalChars": len(original),
        "compressedChars": len(compressed),
    }


def _preserve_structured_fields(value: Mapping[str, object]) -> dict[str, object]:
    preserved: dict[str, object] = {}
    for key in (
        "id",
        "status",
        "error",
        "recordCount",
        "count",
        "citations",
        "references",
    ):
        if key in value:
            preserved[key] = value[key]
    return preserved


def _select_text_for_compression(text: str, *, max_chars: int) -> str:
    """Select high-value regions from the whole text before LLM compression."""
    lines = text.splitlines()
    if not lines:
        return text[:max_chars]

    signal_indexes = {
        index for index, line in enumerate(lines) if TOOL_OUTPUT_SIGNAL_PATTERN.search(line)
    }
    selected: list[int] = []

    def add(index: int) -> None:
        if 0 <= index < len(lines) and index not in selected:
            selected.append(index)

    # Keep signal windows first so a later length limit cannot hide them.
    for index in sorted(signal_indexes):
        for candidate in range(index - 2, index + 3):
            add(candidate)
    for index in range(min(10, len(lines))):
        add(index)
    for index in range(max(0, len(lines) - 20), len(lines)):
        add(index)

    stride = max(1, len(lines) // 40)
    for index in range(0, len(lines), stride):
        add(index)

    selected.sort()
    output: list[str] = []
    size = 0
    for index in selected:
        line = f"[{index + 1}] {lines[index]}"
        separator = "\n" if output else ""
        if size + len(separator) + len(line) > max_chars:
            continue
        output.append(line)
        size += len(separator) + len(line)
    return "\n".join(output)


# ---------------------------------------------------------------------------
# context token estimation
# ---------------------------------------------------------------------------


def estimate_context_tokens(
    *,
    system_prompt: str,
    memory_summary: str | None,
    messages: list[ChatMessageRecord],
    llm_provider: LlmProvider | None = None,
) -> int:
    values: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if memory_summary:
        values.append({"role": "system", "content": _memory_instruction(memory_summary)})
    values.extend(
        {"role": message.role, "content": message.content}
        for message in messages
        if message.role in {"user", "assistant"}
    )
    return sum(count_tokens(item["content"], llm_provider=llm_provider) for item in values)


def count_tokens(text: str, *, llm_provider: LlmProvider | None) -> int:
    """Count with the configured model, falling back to a safe Unicode bound."""
    counter = (
        cast(Callable[[str], int] | None, getattr(llm_provider, "count_tokens", None))
        if llm_provider
        else None
    )
    if callable(counter):
        try:
            return max(0, int(counter(text)))
        except Exception:
            pass
    approximate = int(count_tokens_approximately(cast(Any, [{"role": "user", "content": text}])))
    return max(approximate, len("".join(text.split())))


def memory_payload(session: ChatSessionRecord, context_window_tokens: int) -> dict[str, object]:
    return {
        "mode": session.memory_mode,
        "contextTokens": session.context_tokens,
        "contextWindowTokens": context_window_tokens,
        "contextUsagePercent": _usage_percent(session.context_tokens, context_window_tokens),
        "lastCompactedAt": (
            session.last_compacted_at.isoformat() if session.last_compacted_at is not None else None
        ),
        "lastCompactionError": session.last_compaction_error,
        "lastCompactionFailedAt": (
            session.last_compaction_failed_at.isoformat()
            if session.last_compaction_failed_at is not None
            else None
        ),
        "canCompact": session.context_tokens > 0,
    }


def _candidate_user_message(
    session: ChatSessionRecord, owner_user_id: str, content: str
) -> ChatMessageRecord:
    return ChatMessageRecord(
        id="candidate",
        owner_user_id=owner_user_id,
        session_id=session.id,
        role="user",
        content=content,
        metadata={},
        created_at=datetime.now(timezone.utc),
    )


def _usage_percent(tokens: int, window: int) -> float:
    return round(min(100.0, tokens / window * 100), 1)


def _memory_document(summary: str | None) -> JsonDict:
    if not summary:
        return {"version": MEMORY_SCHEMA_VERSION, "summary": "无", "items": []}
    try:
        parsed = json.loads(summary)
    except json.JSONDecodeError:
        return {"version": 0, "summary": summary, "items": []}
    return (
        cast(dict[str, object], parsed)
        if isinstance(parsed, dict)
        else {"version": 0, "summary": summary, "items": []}
    )


def _memory_source_ids(memory: JsonDict) -> set[str]:
    items = memory.get("items")
    if not isinstance(items, list):
        return set()
    source_ids: set[str] = set()
    for raw_item in cast(list[object], items):
        if not isinstance(raw_item, Mapping):
            continue
        item = cast(Mapping[str, object], raw_item)
        values = item.get("sourceMessageIds")
        if isinstance(values, list):
            source_ids.update(str(value) for value in cast(list[object], values) if value)
    return source_ids


def _validated_memory_document(text: str, *, allowed_source_ids: set[str]) -> JsonDict | None:
    parsed = extract_json_object(text)
    if parsed is None:
        return None
    memory = parsed
    if memory.get("version") != MEMORY_SCHEMA_VERSION:
        return None
    summary = memory.get("summary")
    items = memory.get("items")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1_200:
        return None
    if not isinstance(items, list):
        return None
    normalized_items: list[JsonDict] = []
    for raw_item in cast(list[object], items):
        if not isinstance(raw_item, Mapping):
            return None
        item = cast(Mapping[str, object], raw_item)
        category = item.get("category")
        content = item.get("content")
        source_ids = item.get("sourceMessageIds")
        if (
            not isinstance(category, str)
            or category not in MEMORY_CATEGORIES
            or not isinstance(content, str)
            or not content.strip()
            or not isinstance(source_ids, list)
            or not source_ids
            or not all(
                str(source_id) in allowed_source_ids for source_id in cast(list[object], source_ids)
            )
        ):
            return None
        normalized_items.append(
            {
                "category": category,
                "content": content.strip(),
                "sourceMessageIds": [
                    str(source_id) for source_id in cast(list[object], source_ids)
                ],
            }
        )
    return {"version": MEMORY_SCHEMA_VERSION, "summary": summary.strip(), "items": normalized_items}


def _validate_memory_fidelity(memory: JsonDict, *, source_text: str) -> bool:
    """校验压缩记忆的数字与行动条目可追溯到原文。

    返回 False 表示摘要包含原文无法支撑的声称；调用方应保留上一版记忆。
    """
    source_numbers = _extract_numbers(source_text)
    summary = str(memory.get("summary") or "")
    items = memory.get("items")
    item_list = cast(list[object], items) if isinstance(items, list) else []
    for number in _extract_numbers(summary):
        if number not in source_numbers:
            return False
    for raw_item in item_list:
        if not isinstance(raw_item, Mapping):
            return False
        item = cast(Mapping[str, object], raw_item)
        content = str(item.get("content") or "")
        category = str(item.get("category") or "")
        for number in _extract_numbers(content):
            if number not in source_numbers:
                return False
        if category in {"decision", "todo"} and not _shares_literal_evidence(
            content, source_text
        ):
            return False
    return True


def _extract_numbers(text: str) -> set[str]:
    """提取文本中的数字 token，数字形式错误码也由该集合覆盖。"""
    return set(_MEMORY_NUMBER_PATTERN.findall(text))


def _shares_literal_evidence(content: str, source_text: str) -> bool:
    """判断行动条目是否与原文共享至少一个长度≥2的非数字连续片段。"""
    content_compact = "".join(_MEMORY_NUMBER_PATTERN.sub("", content).split())
    source_compact = "".join(_MEMORY_NUMBER_PATTERN.sub("", source_text).split())
    if len(content_compact) < 2:
        return False
    return any(
        content_compact[index : index + 2] in source_compact
        for index in range(len(content_compact) - 1)
    )


def _compaction_source_text(transcript: str, existing_memory: JsonDict) -> str:
    """拼出压缩输入的原文文本，供摘要忠实性校验比对。"""
    parts = [transcript]
    summary = existing_memory.get("summary")
    if isinstance(summary, str):
        parts.append(summary)
    items = existing_memory.get("items")
    if isinstance(items, list):
        for raw_item in cast(list[object], items):
            if isinstance(raw_item, Mapping):
                content = cast(Mapping[str, object], raw_item).get("content")
                if isinstance(content, str):
                    parts.append(content)
    return "\n".join(parts)


def _select_messages_for_compaction(
    *,
    messages: list[ChatMessageRecord],
    system_prompt: str,
    memory_summary: str | None,
    context_window_tokens: int,
    llm_provider: LlmProvider | None = None,
) -> list[ChatMessageRecord]:
    """Select an old prefix that fits a separate summary-input budget."""
    budget = max(
        MEMORY_COMPACTION_MIN_TOKENS,
        int(context_window_tokens * MEMORY_COMPACTION_INPUT_RATIO),
    )
    selected: list[ChatMessageRecord] = []
    for message in messages:
        candidate = [*selected, message]
        if (
            estimate_context_tokens(
                system_prompt=system_prompt,
                memory_summary=memory_summary,
                messages=candidate,
                llm_provider=llm_provider,
            )
            <= budget
        ):
            selected.append(message)
            continue
        if selected:
            break
        selected.append(
            replace(
                message,
                content=_bounded_text(message.content, MEMORY_COMPACTION_MESSAGE_CAP_CHARS),
            )
        )
        break
    return selected or messages[:1]


def _bounded_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = max(1, limit // 2)
    tail = max(1, limit - head)
    return f"{text[:head]}\n[... 中间内容已省略 ...]\n{text[-tail:]}"


def _runtime_text(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _memory_instruction(summary: str) -> str:
    memory = _memory_document(summary)
    lines = [f"摘要：{memory['summary']}"]
    for item in cast(list[JsonDict], memory["items"]):
        sources = ",".join(str(source) for source in cast(list[object], item["sourceMessageIds"]))
        lines.append(f"- [{item['category']}] {item['content']}（来源：{sources or '未标注'}）")
    return "以下是此前对话的压缩记忆，请作为真实会话上下文继续回答：\n" + "\n".join(lines)


def _prompt_with_memory(system_prompt: str, summary: str | None) -> str:
    return f"{system_prompt}\n\n{_memory_instruction(summary)}" if summary else system_prompt


def _extract_model_text(value: object) -> str:
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        parts: list[str] = []
        for item in cast(Sequence[object], content):
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                text = cast(Mapping[object, object], item).get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""
