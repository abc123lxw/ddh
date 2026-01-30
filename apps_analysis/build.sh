#!/bin/bash

set -e

echo "开始构建 Log Analyzer..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

# 构建Docker镜像
echo "构建Docker镜像..."
docker build -t log-analyzer:latest .

echo "构建完成！"
echo ""
echo "使用方法:"
echo "  docker-compose up -d          # 启动服务"
echo "  docker-compose down            # 停止服务"
echo "  docker-compose logs -f         # 查看日志"
