#!/bin/bash
# AI 面试备战助手 一键启动
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "首次运行：创建虚拟环境并安装依赖（约 1 分钟）..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    || .venv/bin/pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "已生成 .env，请打开项目根目录 .env 填写 DEEPSEEK_API_KEY 后重新运行"
  exit 1
fi

echo "正在启动 AI 面试备战助手：http://localhost:8501"
open http://localhost:8501
exec .venv/bin/streamlit run ui/app.py --server.port 8501 --server.headless true --server.fileWatcherType none
