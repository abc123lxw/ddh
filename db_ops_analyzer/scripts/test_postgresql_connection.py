#!/usr/bin/env python3
"""PostgreSQL连接测试脚本

用于诊断PostgreSQL数据库连接问题
"""

import sys
import socket
import argparse
try:
    import psycopg2
    from psycopg2 import OperationalError
except ImportError:
    print("错误: 需要安装psycopg2库")
    print("安装命令: pip install psycopg2-binary")
    sys.exit(1)


def test_network_connectivity(host, port, timeout=5):
    """测试网络连通性"""
    print(f"\n[1/3] 测试网络连通性: {host}:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ 网络连通性正常: {host}:{port} 端口可访问")
            return True
        else:
            print(f"✗ 网络连通性失败: {host}:{port} 端口不可访问")
            print(f"  错误代码: {result}")
            return False
    except socket.gaierror as e:
        print(f"✗ DNS解析失败: 无法解析主机名 '{host}'")
        print(f"  错误: {e}")
        return False
    except Exception as e:
        print(f"✗ 网络测试失败: {e}")
        return False


def test_postgresql_connection(host, port, user, password, database=None, timeout=10):
    """测试PostgreSQL连接"""
    print(f"\n[2/3] 测试PostgreSQL连接")
    print(f"  主机: {host}")
    print(f"  端口: {port}")
    print(f"  用户: {user}")
    print(f"  数据库: {database or '(未指定)'}")
    
    try:
        conn_params = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'connect_timeout': timeout
        }
        if database:
            conn_params['database'] = database
        
        conn = psycopg2.connect(**conn_params)
        print("✓ PostgreSQL连接成功!")
        
        # 获取数据库版本信息
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"  数据库版本: {version.split(',')[0]}")
        
        # 获取当前数据库
        cursor.execute("SELECT current_database();")
        current_db = cursor.fetchone()[0]
        print(f"  当前数据库: {current_db}")
        
        # 检查监听地址
        cursor.execute("SHOW listen_addresses;")
        listen_addresses = cursor.fetchone()[0]
        print(f"  监听地址: {listen_addresses}")
        
        cursor.close()
        conn.close()
        return True
        
    except OperationalError as e:
        error_str = str(e)
        print(f"✗ PostgreSQL连接失败!")
        
        if "could not connect" in error_str.lower() or "connection refused" in error_str.lower():
            print("\n可能的原因:")
            print("1. PostgreSQL服务未运行")
            print("2. PostgreSQL未监听该IP地址")
            print("   - 检查 postgresql.conf 中的 listen_addresses 配置")
            print("   - 如果只配置了 'localhost'，外部无法连接")
            print("   - 建议配置为 '*' 或具体IP地址")
            print("3. 防火墙阻止了连接")
            print("4. 如果db_ops_analyzer运行在Docker容器中:")
            print("   - 需要使用容器名称（如 windmill-db-1）或Docker网络IP")
            print("   - 而不是 'localhost' 或主机IP")
            print("   - 确保两个容器在同一个Docker网络中")
        elif "timeout" in error_str.lower():
            print("\n可能的原因:")
            print("1. 网络不通或防火墙阻止")
            print("2. 主机地址不正确")
            print("3. PostgreSQL服务响应慢")
        elif "authentication failed" in error_str.lower() or "password" in error_str.lower():
            print("\n可能的原因:")
            print("1. 用户名或密码错误")
            print("2. PostgreSQL的pg_hba.conf配置不允许该用户从该地址连接")
        elif "database" in error_str.lower() and "does not exist" in error_str.lower():
            print("\n可能的原因:")
            print("1. 指定的数据库不存在")
            print("2. 数据库名称拼写错误")
        else:
            print(f"\n错误详情: {error_str}")
        
        return False
    except Exception as e:
        print(f"✗ 连接测试失败: {e}")
        return False


def provide_suggestions(host, port):
    """提供连接建议"""
    print(f"\n[3/3] 连接建议")
    
    if host == "localhost" or host == "127.0.0.1":
        print("\n⚠️  检测到使用 'localhost' 连接")
        print("如果db_ops_analyzer运行在Docker容器中，建议:")
        print("1. 使用PostgreSQL容器的服务名称（如 windmill-db-1）")
        print("2. 或使用Docker网络的IP地址")
        print("3. 确保两个容器在同一个Docker网络中")
        print("\n检查Docker网络:")
        print("  docker network ls")
        print("  docker network inspect <network_name>")
    
    print("\n检查PostgreSQL配置:")
    print("1. 查看 listen_addresses:")
    print("   docker exec windmill-db-1 psql -U postgres -c \"SHOW listen_addresses;\"")
    print("\n2. 查看 pg_hba.conf:")
    print("   docker exec windmill-db-1 cat /var/lib/postgresql/data/pg_hba.conf")
    print("\n3. 如果需要允许外部连接，修改 postgresql.conf:")
    print("   listen_addresses = '*'")
    print("   然后重启PostgreSQL容器")


def main():
    parser = argparse.ArgumentParser(description="PostgreSQL连接测试工具")
    parser.add_argument("--host", default="localhost", help="PostgreSQL主机地址")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL端口")
    parser.add_argument("--user", default="postgres", help="PostgreSQL用户名")
    parser.add_argument("--password", required=True, help="PostgreSQL密码")
    parser.add_argument("--database", help="数据库名称（可选）")
    parser.add_argument("--timeout", type=int, default=10, help="连接超时时间（秒）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PostgreSQL连接诊断工具")
    print("=" * 60)
    
    # 测试网络连通性
    network_ok = test_network_connectivity(args.host, args.port, timeout=5)
    
    if not network_ok:
        print("\n⚠️  网络连通性测试失败，但仍会尝试PostgreSQL连接...")
    
    # 测试PostgreSQL连接
    pg_ok = test_postgresql_connection(
        args.host, args.port, args.user, args.password, 
        args.database, timeout=args.timeout
    )
    
    # 提供建议
    provide_suggestions(args.host, args.port)
    
    print("\n" + "=" * 60)
    if pg_ok:
        print("✓ 所有测试通过！连接配置正确。")
        return 0
    else:
        print("✗ 连接测试失败，请根据上述建议进行排查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
