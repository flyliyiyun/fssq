# === FSSQ 风生水起 Dockerfile ===
# 多阶段构建：builder安装依赖 + runtime运行
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装依赖（仅安装requirements中非注释行）
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# === 运行时镜像 ===
FROM python:3.11-slim

WORKDIR /app

# 从builder复制已安装的包
COPY --from=builder /install /usr/local

# 复制项目代码
COPY src/ src/
COPY run_pipeline.py .
COPY requirements.txt .

# 创建输出目录
RUN mkdir -p output src/output

# 环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# 默认端口（未来Web服务用）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import sys; sys.path.insert(0,'src'); from orchestrator import FSSQOrchestrator; print('OK')" || exit 1

# 默认入口：显示帮助
CMD ["python3", "run_pipeline.py", "--help"]
