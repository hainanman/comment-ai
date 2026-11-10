#!/usr/bin/env bash
# PythonAnywhere 一键初始化：虚拟环境 + 依赖 + .env + 演示数据
set -e
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

echo "== 1/4 创建虚拟环境 =="
if [ ! -d venv ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "== 2/4 安装依赖 =="
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "== 3/4 生成 .env =="
if [ ! -f .env ]; then
  SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
  cat > .env <<ENVEOF
FLASK_SECRET_KEY=${SECRET}
DATABASE_URL=sqlite:///${PROJECT_DIR}/instance/comment_ai.db
# 免费版外网受限，AI 默认走规则兜底；确认能访问 dashscope 后改成 true 并填 Key
AI_ENABLED=false
DASHSCOPE_API_KEY=
LLM_JSON_MODE=true
REVIEW_THRESHOLD=0.50
REJECT_THRESHOLD=0.85
DAILY_LLM_LIMIT=300
SESSION_COOKIE_SECURE=true
ENVEOF
  echo "已生成 .env"
else
  echo ".env 已存在，跳过"
fi

echo "== 4/4 初始化演示数据 =="
mkdir -p instance
python seed.py --reset

echo
echo "初始化完成。项目路径：${PROJECT_DIR}"
echo "下一步：Web 标签页配置 WSGI 与 static 映射，然后 Reload。"
