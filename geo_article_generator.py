from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    app_path = Path(__file__).with_name("app.py")
    print("GEO 第一版已迁移到 Streamlit UI。")
    print("正在尝试启动：streamlit run app.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=False)


if __name__ == "__main__":
    main()

