FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 海外平台默认走官方源；国内构建可用 --build-arg PIP_INDEX_URL=镜像地址 覆盖
ARG PIP_INDEX_URL=https://pypi.org/simple/
COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.txt

COPY . .

# 数据目录（SQLite）与静态资源
RUN mkdir -p /app/instance

EXPOSE 8000

CMD ["python", "run_server.py"]
