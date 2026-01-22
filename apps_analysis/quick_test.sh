#!/bin/bash
# 快速测试脚本 - 用于离线环境

set -e

echo "=========================================="
echo "Log Analyzer 快速测试"
echo "=========================================="
echo ""

# 1. 检查镜像
echo "[1/8] 检查镜像..."
if docker images | grep -q "log-analyzer"; then
    echo "✓ 镜像已加载"
    docker images | grep log-analyzer
else
    echo "✗ 镜像未找到，请先加载: docker load -i log-analyzer.tar"
    exit 1
fi
echo ""

# 2. 检查容器
echo "[2/8] 检查要分析的容器..."
containers=("dispatcher" "agent_python" "mcp_server")
missing=0
for container in "${containers[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "✓ $container 正在运行"
    else
        echo "✗ $container 未运行"
        missing=1
    fi
done
if [ $missing -eq 1 ]; then
    echo "警告: 部分容器未运行，分析可能失败"
fi
echo ""

# 3. 检查配置文件
echo "[3/8] 检查配置文件..."
if [ -f "config.yaml" ]; then
    echo "✓ config.yaml 存在"
else
    echo "✗ config.yaml 不存在"
    exit 1
fi
echo ""

# 4. 启动服务
echo "[4/8] 启动API服务..."
if docker ps | grep -q "log-analyzer"; then
    echo "✓ 服务已在运行"
else
    docker-compose up -d log-analyzer 2>/dev/null || \
    docker run -d \
      --name log-analyzer \
      -p 8000:8000 \
      -v $(pwd)/config.yaml:/app/config.yaml:ro \
      -v $(pwd)/reports:/app/reports \
      -v /var/run/docker.sock:/var/run/docker.sock:ro \
      -e CONFIG_PATH=/app/config.yaml \
      log-analyzer:latest
    echo "✓ 服务已启动，等待5秒..."
    sleep 5
fi
echo ""

# 5. 健康检查
echo "[5/8] 健康检查..."
response=$(curl -s http://localhost:8000/health 2>/dev/null || echo "ERROR")
if echo "$response" | grep -q "healthy"; then
    echo "✓ 服务健康: $response"
else
    echo "✗ 服务异常: $response"
    echo "查看日志: docker logs log-analyzer"
    exit 1
fi
echo ""

# 6. 列出任务
echo "[6/8] 列出任务..."
curl -s http://localhost:8000/api/tasks | python3 -m json.tool 2>/dev/null || \
curl -s http://localhost:8000/api/tasks
echo ""

# 7. 测试单个服务分析（最近10分钟）
echo "[7/8] 测试单个服务分析（dispatcher，最近10分钟）..."
docker run --rm \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/reports:/app/reports \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -e CONFIG_PATH=/app/config.yaml \
  -e CONTAINER_NAME=dispatcher \
  -e MINUTES_AGO=10 \
  log-analyzer:latest \
  python /app/scripts/analyze_service.py

if [ $? -eq 0 ]; then
    echo "✓ 分析完成"
else
    echo "✗ 分析失败"
fi
echo ""

# 8. 查看报告
echo "[8/8] 查看报告..."
if [ -d "reports" ] && [ "$(ls -A reports/*.md 2>/dev/null)" ]; then
    echo "✓ 找到报告文件:"
    ls -lh reports/*.md | tail -3
    echo ""
    echo "最新报告内容（前20行）:"
    ls -t reports/*.md | head -1 | xargs head -20
else
    echo "⚠ 暂无报告文件"
fi
echo ""

echo "=========================================="
echo "测试完成！"
echo "=========================================="
echo ""
echo "下一步:"
echo "1. 查看完整报告: ls -t reports/*.md | head -1 | xargs cat"
echo "2. 通过API触发分析: curl -X POST 'http://localhost:8000/api/tasks/Three_Apps_Error_Analysis/run?minutes_ago=30'"
echo "3. 查看API文档: http://localhost:8000/docs"
