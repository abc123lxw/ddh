#!/bin/bash
# 分析单个服务的错误日志脚本
# 用于Docker Compose触发

set -e

CONTAINER_NAME=${CONTAINER_NAME:-""}
MINUTES_AGO=${MINUTES_AGO:-""}
HOURS_AGO=${HOURS_AGO:-""}
SINCE=${SINCE:-""}
UNTIL=${UNTIL:-""}
TASK=${TASK:-""}

if [ -z "$CONTAINER_NAME" ] && [ -z "$TASK" ]; then
    echo "错误: 必须指定 CONTAINER_NAME 或 TASK 环境变量"
    exit 1
fi

# 构建命令
CMD="python -m log_analyzer.main --config /app/config.yaml"

if [ -n "$CONTAINER_NAME" ]; then
    CMD="$CMD --container $CONTAINER_NAME"
fi

if [ -n "$TASK" ]; then
    CMD="$CMD --task $TASK"
fi

if [ -n "$MINUTES_AGO" ]; then
    CMD="$CMD --minutes-ago $MINUTES_AGO"
fi

if [ -n "$HOURS_AGO" ]; then
    CMD="$CMD --hours-ago $HOURS_AGO"
fi

if [ -n "$SINCE" ]; then
    CMD="$CMD --since \"$SINCE\""
fi

if [ -n "$UNTIL" ]; then
    CMD="$CMD --until \"$UNTIL\""
fi

echo "执行命令: $CMD"
exec $CMD
