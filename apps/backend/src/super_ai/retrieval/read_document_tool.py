"""Agent-facing tool to read full document content by ID.

Unlike knowledge_retrieval (which returns chunked search results), this tool
returns the complete plain-text content of a single document so the Agent can
answer detailed questions that span multiple chunks.
"""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from super_ai.memory.repositories import KnowledgeDocumentRepository

READ_DOCUMENT_TOOL_NAME = "read_document"
MAX_DOCUMENT_LENGTH_CHARS = 24_000


class ReadDocumentInput(BaseModel):
    """Arguments accepted by the read_document tool."""

    document_id: str = Field(
        description=(
            "The document ID to read (e.g. 'doc_abc123'). "
            "You can find document IDs in knowledge_retrieval results under 'documentId'."
        ),
    )


def create_read_document_tool(
    *,
    owner_user_id: str,
    accessible_knowledge_base_ids: Sequence[str],
    document_repository: KnowledgeDocumentRepository,
) -> StructuredTool:
    """Create a request-scoped LangChain tool that reads full document text."""

    async def read_document(document_id: str) -> str:
        doc_id = document_id.strip()
        if not doc_id:
            return "Error: document_id is required."

        for kb_id in accessible_knowledge_base_ids:
            doc = await document_repository.get_document(
                owner_user_id=owner_user_id,
                knowledge_base_id=kb_id,
                document_id=doc_id,
            )
            if doc is None:
                continue

            text = doc.metadata.get("indexableText") if doc.metadata else None
            if not isinstance(text, str) or not text.strip():
                return (
                    f"Document '{doc.filename}' ({doc_id}) exists but has no "
                    f"readable text content. Status: {doc.status}, "
                    f"Index status: {doc.index_status}."
                )

            truncated = text if len(text) <= MAX_DOCUMENT_LENGTH_CHARS else (
                f"{text[:MAX_DOCUMENT_LENGTH_CHARS - 200]}\n\n"
                f"[... 文档过长，已截断。原文共 {len(text)} 字符，"
                f"以上为前 {MAX_DOCUMENT_LENGTH_CHARS} 字符。"
                f"如需查阅后半部分，请使用 knowledge_retrieval 工具搜索具体关键词。]"
            )
            return f"# {doc.filename}\n\n{truncated}"

        return (
            f"Document '{doc_id}' not found in your accessible knowledge bases. "
            f"Available knowledge bases: {', '.join(accessible_knowledge_base_ids) or 'none'}."
        )

    return StructuredTool.from_function(
        coroutine=read_document,
        name=READ_DOCUMENT_TOOL_NAME,
        description=(
            "Read the complete text of a single knowledge base document by its ID. "
            "Use this when you need the full document content rather than search "
            "snippets — for example, to answer detailed questions, verify facts "
            "across sections, or read SOPs and runbooks in full. "
            "The document ID can be found in knowledge_retrieval results (the "
            "'documentId' field)."
        ),
        args_schema=ReadDocumentInput,
    )
