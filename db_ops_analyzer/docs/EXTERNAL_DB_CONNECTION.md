# 连接外部数据库配置指南

## 问题描述

当 `db_ops_analyzer` 运行在 Docker 容器中，需要连接外部数据库服务器（如 `10.163.25.156:54322`）时，可能会遇到连接超时的问题。

## 原因分析

Docker 容器默认使用 bridge 网络模式，容器内的网络与主机网络隔离。容器无法直接访问主机的网络接口，因此无法连接到外部数据库服务器。

## 解决方案

### 方案1: 使用 Host 网络模式（推荐）

修改 `docker-compose.yml`，添加 `network_mode: "host"`：

```yaml
services:
  db-ops-analyzer:
    image: db-ops-analyzer:latest
    container_name: db-ops-analyzer
    network_mode: "host"  # 使用主机网络
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./reports:/app/reports
    environment:
      - CONFIG_PATH=/app/config.yaml
    restart: unless-stopped
```

**优点**：
- 容器可以直接访问主机网络
- 可以连接到任何主机可以访问的外部数据库
- 配置简单

**缺点**：
- 端口映射会被忽略（服务直接监听8000端口）
- 安全性稍低（容器直接使用主机网络）

**使用方式**：
```bash
docker-compose up -d
# 访问地址: http://localhost:8000
```

### 方案2: 使用 Docker 网络别名

如果数据库也在 Docker 容器中，可以使用 Docker 网络：

```yaml
services:
  db-ops-analyzer:
    image: db-ops-analyzer:latest
    container_name: db-ops-analyzer
    ports:
      - "8006:8000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./reports:/app/reports
    environment:
      - CONFIG_PATH=/app/config.yaml
    networks:
      - db_network
    extra_hosts:
      - "postgres-host:10.163.25.156"  # 添加主机映射

networks:
  db_network:
    driver: bridge
```

然后在配置中使用 `postgres-host` 作为主机地址。

### 方案3: 使用 host.docker.internal（Windows/Mac）

在 Windows 或 Mac 上，可以使用 `host.docker.internal` 访问主机：

```yaml
services:
  db-ops-analyzer:
    image: db-ops-analyzer:latest
    container_name: db-ops-analyzer
    ports:
      - "8006:8000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./reports:/app/reports
    environment:
      - CONFIG_PATH=/app/config.yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"  # 访问主机网络
```

然后在配置中使用 `host.docker.internal` 或直接使用外部IP。

### 方案4: 直接运行（不使用Docker）

如果网络配置复杂，也可以直接在主机上运行：

```bash
cd db_ops_analyzer
pip install -e .
python -m db_ops_analyzer.server
```

## 针对您的具体情况

您的数据库信息：
- 主机: `10.163.25.156`
- 端口: `54322`
- 数据库: `postgres`
- 用户名: `postgres`
- 密码: `ddh2025`

**推荐方案**：使用 Host 网络模式

1. 修改 `docker-compose.yml`（已更新）
2. 重启容器：
   ```bash
   docker-compose down
   docker-compose up -d
   ```
3. 在页面上填写连接信息：
   - 主机地址: `10.163.25.156`
   - 端口: `54322`
   - 数据库名: `postgres`
   - 用户名: `postgres`
   - 密码: `ddh2025`

## 验证连接

### 方法1: 在容器内测试

```bash
docker exec -it db-ops-analyzer python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='10.163.25.156',
        port=54322,
        user='postgres',
        password='ddh2025',
        database='postgres',
        connect_timeout=10
    )
    print('Connection successful!')
    conn.close()
except Exception as e:
    print(f'Connection failed: {e}')
"
```

### 方法2: 使用诊断脚本

```bash
docker exec -it db-ops-analyzer python /app/scripts/test_postgresql_connection.py \
  --host 10.163.25.156 \
  --port 54322 \
  --user postgres \
  --password ddh2025 \
  --database postgres
```

## 常见问题

### Q: 连接仍然超时怎么办？

1. **检查网络连通性**：
   ```bash
   # 在主机上测试
   telnet 10.163.25.156 54322
   # 或
   nc -zv 10.163.25.156 54322
   ```

2. **检查防火墙**：
   - 确保主机防火墙允许访问 `10.163.25.156:54322`
   - 确保数据库服务器的防火墙允许来自主机的连接

3. **检查PostgreSQL配置**：
   - 确保 `postgresql.conf` 中 `listen_addresses` 包含 `*` 或具体IP
   - 确保 `pg_hba.conf` 允许来自主机的连接

### Q: 使用host网络模式后端口冲突？

如果8000端口被占用，可以：
1. 修改代码中的端口配置
2. 或者停止占用8000端口的服务

### Q: 如何在不使用host网络的情况下连接外部数据库？

可以使用 `extra_hosts` 配置，或者使用 `host.docker.internal`（Windows/Mac）。

## 总结

对于连接外部数据库服务器，**推荐使用 Host 网络模式**，这是最简单且最可靠的方式。
