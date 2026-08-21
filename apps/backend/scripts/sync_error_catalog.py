"""Sync the backend error catalog into the shared api-contracts JSON.

以 ``super_ai.error_catalog.ERROR_DEFINITIONS`` 为单一事实来源，生成
``packages/api-contracts/src/generated/error-catalog.json`` 供前端契约测试
断言 `errors.ts` 与后端错误码双向一致。CI 通过 ``git diff --exit-code``
校验生成文件未过期。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    REPO_ROOT
    / "packages"
    / "api-contracts"
    / "src"
    / "generated"
    / "error-catalog.json"
)


def main() -> None:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "backend" / "src"))
    from super_ai.error_catalog import ERROR_DEFINITIONS

    catalog = {
        code: {"category": category, "httpStatus": http_status, "message": message}
        for code, (category, http_status, message) in sorted(ERROR_DEFINITIONS.items())
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT} ({len(catalog)} error codes)")


if __name__ == "__main__":
    main()
