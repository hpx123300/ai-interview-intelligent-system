#!/bin/bash
# AI 面试备战助手 一键启动
# 双击本文件：自动创建虚拟环境 → 启动服务 → 等服务就绪后自动打开浏览器

cd "$(dirname "$0")" || exit 1

# 1. 首次运行：创建虚拟环境并安装依赖
if [ ! -d ".venv" ]; then
  echo "首次运行：创建虚拟环境并安装依赖（可能需要 1-2 分钟）..."
  python3 -m venv .venv || exit 1
  .venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    || .venv/bin/pip install -r requirements.txt \
    || exit 1
fi

# 2. 配置文件检查（没有 .env 就自动生成）
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "已生成 .env 文件。"
fi
if ! grep -q "^DEEPSEEK_API_KEY=.\+" .env 2>/dev/null; then
  echo "提示：.env 里还没有填写 DEEPSEEK_API_KEY，界面可以打开，"
  echo "但 AI 功能需要填写 Key 后重新运行本文件才能使用。"
fi

# 3. 端口占用检查：如果已经在运行，直接打开浏览器
if lsof -nP -iTCP:8501 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "服务已在运行，正在打开浏览器：http://localhost:8501"
  open http://localhost:8501
  exit 0
fi

# 4. 后台启动服务
echo "正在启动 AI 面试备战助手，请稍候…"
.venv/bin/streamlit run ui/app.py \
  --server.port 8501 \
  --server.headless true \
  --server.fileWatcherType none &
SERVER_PID=$!

# 5. 等服务就绪后再打开浏览器（最多 60 秒）
READY=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8501/_stcore/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" = "1" ]; then
  echo "启动完成，正在打开浏览器：http://localhost:8501"
  open http://localhost:8501
else
  echo "服务启动超时，请看上方错误信息；也可手动打开 http://localhost:8501"
fi

# 6. 保持前台运行，关闭本窗口即停止服务
wait $SERVER_PID
