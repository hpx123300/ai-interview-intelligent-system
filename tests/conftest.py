"""测试公共配置：保证从项目根导入，并初始化数据库。"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import init_db  # noqa: E402

init_db()
