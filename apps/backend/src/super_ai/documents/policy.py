"""Shared backend policy for user-uploaded knowledge documents."""

DOCUMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENT_EXTENSIONS = frozenset({".md", ".pdf", ".docx"})
MARKDOWN_DOCUMENT_MIME_TYPES = frozenset(
    {"", "application/octet-stream", "text/markdown", "text/plain"}
)
PDF_DOCUMENT_MIME_TYPES = frozenset({"", "application/octet-stream", "application/pdf"})
DOCX_DOCUMENT_MIME_TYPES = frozenset(
    {
        "",
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
ALLOWED_DOCUMENT_MIME_TYPES = (
    MARKDOWN_DOCUMENT_MIME_TYPES | PDF_DOCUMENT_MIME_TYPES | DOCX_DOCUMENT_MIME_TYPES
)
