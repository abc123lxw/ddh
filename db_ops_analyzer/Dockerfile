FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY pyproject.toml ./
COPY db_ops_analyzer ./db_ops_analyzer/
COPY config.yaml ./
COPY static ./static/

# 安装Python依赖
RUN pip install --no-cache-dir -e .

# 创建报告目录
RUN mkdir -p /app/reports

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "db_ops_analyzer.server"]
