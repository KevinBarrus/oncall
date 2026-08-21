"""Enforce per-domain coverage thresholds for critical modules.

配合 ``pytest --cov`` 生成的 ``coverage.json`` 使用：按目录聚合统计
auth / chat / aiops 三大关键域的行覆盖率，低于阈值时非零退出（CI 失败）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CRITICAL_DOMAINS = {
    "super_ai/auth": 0.80,
    "super_ai/chat": 0.75,
    "super_ai/aiops": 0.75,
}


def main() -> None:
    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        print("coverage.json not found; run pytest with --cov-report=json first.")
        sys.exit(1)
    data = json.loads(coverage_file.read_text(encoding="utf-8"))
    files = data["files"]
    failures: list[str] = []
    for domain, threshold in CRITICAL_DOMAINS.items():
        covered = sum(
            file_data["summary"]["covered_lines"]
            for name, file_data in files.items()
            if domain in name
        )
        statements = sum(
            file_data["summary"]["num_statements"]
            for name, file_data in files.items()
            if domain in name
        )
        percent = covered / statements * 100 if statements else 100.0
        status = "OK  " if percent >= threshold * 100 else "FAIL"
        print(f"{status} {domain}: {percent:.1f}% (threshold {threshold * 100:.0f}%)")
        if percent < threshold * 100:
            failures.append(domain)
    if failures:
        print(f"Domain coverage thresholds not met: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
