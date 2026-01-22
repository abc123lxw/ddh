#!/bin/bash
# 导出Docker镜像为tar包（用于离线部署）

set -e

IMAGE_NAME="log-analyzer:latest"
OUTPUT_FILE="log-analyzer.tar"
COMPRESSED_FILE="log-analyzer.tar.gz"

echo "开始导出镜像: $IMAGE_NAME"

# 检查镜像是否存在
if ! docker images | grep -q "log-analyzer"; then
    echo "错误: 镜像 $IMAGE_NAME 不存在"
    echo "请先构建镜像: docker build -t $IMAGE_NAME ."
    exit 1
fi

# 导出镜像
echo "导出镜像到 $OUTPUT_FILE ..."
docker save $IMAGE_NAME -o $OUTPUT_FILE

# 压缩镜像（可选）
echo "压缩镜像到 $COMPRESSED_FILE ..."
gzip -c $OUTPUT_FILE > $COMPRESSED_FILE

# 显示文件大小
echo ""
echo "导出完成！"
echo "文件大小:"
ls -lh $OUTPUT_FILE $COMPRESSED_FILE 2>/dev/null || ls -lh $OUTPUT_FILE

echo ""
echo "使用方法:"
echo "1. 将 $OUTPUT_FILE 或 $COMPRESSED_FILE 传输到离线环境"
echo "2. 在离线环境加载: docker load -i $OUTPUT_FILE"
echo "   或: gunzip -c $COMPRESSED_FILE | docker load"
