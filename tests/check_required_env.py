from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(ROOT_DIR / ".env")


def _first_present(*names: str) -> tuple[bool, str]:
    for name in names:
        value = os.getenv(name, "").strip()
        if value and not value.lower().startswith(("your-", "sk-your", "真实")):
            return True, name
    return False, "/".join(names)


def main() -> int:
    _load_dotenv()
    checks = [
        ("Qwen", ("DASHSCOPE_API_KEY",), True),
        ("Doubao", ("DOUBAO_API_KEY", "ARK_API_KEY", "VOLCENGINE_API_KEY"), True),
        ("Yuanbao/Hunyuan", ("YUANBAO_API_KEY", "HUNYUAN_API_KEY", "TENCENT_HUNYUAN_API_KEY"), True),
        ("DeepSeek", ("DEEPSEEK_API_KEY",), True),
        ("Meijieku mobile", ("MEIJIEKU_MOBILE",), True),
        ("Meijieku password/token", ("MEIJIEKU_PASSWORD", "MEIJIEKU_TOKEN"), True),
        ("Baidu search", ("BAIDU_API_KEY", "BAIDU_QIANFAN_API_KEY", "BAIDU_SEARCH_API_KEY"), False),
        ("SerpApi", ("SERPAPI_API_KEY",), False),
    ]

    missing_required = []
    for label, names, required in checks:
        ok, source = _first_present(*names)
        status = "OK" if ok else ("MISSING" if required else "OPTIONAL")
        print(f"{status:8} {label:22} {source}")
        if required and not ok:
            missing_required.append(label)

    if missing_required:
        print("\nMissing required config: " + ", ".join(missing_required))
        print("Copy .env.example to .env, then fill real values through a private channel.")
        return 1
    print("\nRequired environment variables are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
