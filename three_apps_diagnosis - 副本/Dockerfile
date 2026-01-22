FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 注意：不需要在容器内安装Docker
# 只需要挂载主机的 /var/run/docker.sock 即可访问Docker API

# 复制项目文件
COPY pyproject.toml ./
COPY log_analyzer ./log_analyzer/
COPY config.yaml ./
COPY scripts ./scripts/
COPY static ./static/

# 安装Python依赖
RUN pip install --no-cache-dir -e .

# 创建报告目录
RUN mkdir -p /app/reports

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "log_analyzer.server"]
