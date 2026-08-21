"""Secret-safe logging: structured events and plain message sanitization tests."""

from __future__ import annotations

import logging

import pytest

from super_ai.observability import SanitizingFormatter, configure_structured_logging


def test_sanitizing_formatter_redacts_sensitive_json_pairs() -> None:
    formatter = SanitizingFormatter("%(message)s")
    record = logging.LogRecord(
        "super_ai.test",
        logging.ERROR,
        __file__,
        1,
        'connect failed: {"apiKey": "sk-live-999", "region": "ap-guangzhou"}',
        (),
        None,
    )
    rendered = formatter.format(record)
    assert "sk-live-999" not in rendered
    assert "apiKey" in rendered and "***" in rendered
    assert "ap-guangzhou" in rendered


def test_sanitizing_formatter_redacts_args_expanded_values() -> None:
    formatter = SanitizingFormatter("%(message)s")
    record = logging.LogRecord(
        "super_ai.test",
        logging.ERROR,
        __file__,
        1,
        "upload failed: %s",
        ('{"secretKey": "abc-123", "password": "p@ss", "size": 10}',),
        None,
    )
    rendered = formatter.format(record)
    assert "abc-123" not in rendered
    assert "p@ss" not in rendered
    assert "secretKey" in rendered and "***" in rendered
    assert "size" in rendered


def test_sanitizing_formatter_redacts_equals_style_pairs() -> None:
    formatter = SanitizingFormatter("%(message)s")
    record = logging.LogRecord(
        "super_ai.test",
        logging.WARNING,
        __file__,
        1,
        "auth token=sk-token-42 expired",
        (),
        None,
    )
    rendered = formatter.format(record)
    assert "sk-token-42" not in rendered
    assert "token=***" in rendered


def test_sanitizing_formatter_keeps_plain_messages_unchanged() -> None:
    formatter = SanitizingFormatter("%(message)s")
    record = logging.LogRecord(
        "super_ai.test",
        logging.INFO,
        __file__,
        1,
        "context budget reached 95%, compaction scheduled",
        (),
        None,
    )
    assert formatter.format(record) == record.getMessage()


def test_configured_logger_sanitizes_plain_output(capsys: pytest.CaptureFixture[str]) -> None:
    configure_structured_logging()
    logger = logging.getLogger("super_ai.sanitization_test")
    logger.error("credential leak: %s", 'apiKey="sk-visible-7"')
    captured = capsys.readouterr().err
    assert "sk-visible-7" not in captured
