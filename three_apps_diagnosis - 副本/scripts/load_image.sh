#!/bin/bash
# 在离线环境加载Docker镜像

set -e

IMAGE_FILE="${1:-log-analyzer.tar}"

if [ ! -f "$IMAGE_FILE" ]; then
    echo "错误: 镜像文件不存在: $IMAGE_FILE"
    echo "使用方法: $0 [镜像文件路径]"
    echo "示例: $0 log-analyzer.tar"
    exit 1
fi

echo "加载镜像: $IMAGE_FILE"

# 如果是压缩文件，先解压
if [[ "$IMAGE_FILE" == *.gz ]]; then
    echo "检测到压缩文件，解压中..."
    gunzip -c "$IMAGE_FILE" | docker load
else
    docker load -i "$IMAGE_FILE"
fi

echo ""
echo "镜像加载成功！"
echo "验证镜像:"
docker images | grep log-analyzer

echo ""
echo "下一步:"
echo "1. 准备 config.yaml 配置文件"
echo "2. 启动服务: docker-compose up -d"
echo "   或: docker run -d --name log-analyzer -p 8000:8000 ..."
