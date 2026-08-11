"""测试公共配置：保证从项目根导入，并初始化数据库。"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# CI / 无 .env 环境下也能跑：配置一个占位 Key（所有 LLM 调用均被 mock）
os.environ.setdefault("DEEPSEEK_API_KEY", "test-dummy-key")

from backend.app.db import init_db  # noqa: E402

init_db()
