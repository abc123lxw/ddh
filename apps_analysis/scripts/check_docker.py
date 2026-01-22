#!/usr/bin/env python3
"""检查Docker容器是否可访问"""

import subprocess
import sys

def check_docker():
    """检查Docker是否可用"""
    try:
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ Docker 可用")
            print("\n当前运行的容器:")
            print(result.stdout)
            return True
        else:
            print("✗ Docker 不可用")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("✗ Docker 未安装或不在PATH中")
        return False
    except subprocess.TimeoutExpired:
        print("✗ Docker 命令超时")
        return False
    except Exception as e:
        print(f"✗ 检查Docker时出错: {e}")
        return False

if __name__ == "__main__":
    success = check_docker()
    sys.exit(0 if success else 1)
