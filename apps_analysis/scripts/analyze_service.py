#!/usr/bin/env python3
"""分析单个服务的错误日志脚本（用于Docker Compose）"""

import os
import sys
from log_analyzer.main import main

if __name__ == "__main__":
    # 从环境变量读取参数
    container_name = os.getenv('CONTAINER_NAME')
    task = os.getenv('TASK')
    minutes_ago = os.getenv('MINUTES_AGO')
    hours_ago = os.getenv('HOURS_AGO')
    since = os.getenv('SINCE')
    until = os.getenv('UNTIL')
    config_path = os.getenv('CONFIG_PATH', '/app/config.yaml')
    
    # 构建参数列表
    args = ['--config', config_path]
    
    if container_name:
        args.extend(['--container', container_name])
    elif task:
        args.extend(['--task', task])
    else:
        print("错误: 必须指定 CONTAINER_NAME 或 TASK 环境变量", file=sys.stderr)
        sys.exit(1)
    
    if minutes_ago:
        args.extend(['--minutes-ago', minutes_ago])
    if hours_ago:
        args.extend(['--hours-ago', hours_ago])
    if since:
        args.extend(['--since', since])
    if until:
        args.extend(['--until', until])
    
    # 设置sys.argv
    sys.argv = ['analyze_service'] + args
    
    # 执行main函数
    sys.exit(main())
