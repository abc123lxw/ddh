#!/usr/bin/env python3
"""验证 config.yaml 文件格式"""

import yaml
import sys

def validate_config(config_path="config.yaml"):
    """验证配置文件格式"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 验证基本结构
        if not isinstance(data, dict):
            print(f"错误: 配置文件根节点必须是字典")
            return False
        
        if 'server' not in data:
            print(f"错误: 缺少 'server' 配置")
            return False
        
        if 'tasks' not in data:
            print(f"错误: 缺少 'tasks' 配置")
            return False
        
        tasks = data.get('tasks', [])
        if not isinstance(tasks, list):
            print(f"错误: 'tasks' 必须是列表")
            return False
        
        print(f"✅ 配置文件格式正确")
        print(f"   - 服务器配置: {data.get('server')}")
        print(f"   - 任务数量: {len(tasks)}")
        for i, task in enumerate(tasks, 1):
            print(f"   - 任务 {i}: {task.get('name', 'Unknown')}")
        
        return True
    except yaml.YAMLError as e:
        print(f"❌ YAML 解析错误: {e}")
        if hasattr(e, 'problem_mark'):
            print(f"   位置: 行 {e.problem_mark.line + 1}, 列 {e.problem_mark.column + 1}")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    success = validate_config(config_path)
    sys.exit(0 if success else 1)
