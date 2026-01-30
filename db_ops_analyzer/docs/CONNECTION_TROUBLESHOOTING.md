# PostgreSQL连接问题排查指南

## 问题现象

执行数据库分析时出现连接失败，错误信息可能显示：
- "LLM API错误: Request timed out"（这是误导性的错误信息）
- "无法连接到PostgreSQL数据库"
- "连接被拒绝"

## 常见原因和解决方案

### 1. Docker容器网络问题

**问题**: 如果 `db_ops_analyzer` 和 `windmill-db-1` 都运行在Docker容器中，使用 `localhost` 无法连接。

**解决方案**:

#### 方案A: 使用容器服务名称（推荐）

如果两个容器在同一个Docker网络中，使用PostgreSQL容器的服务名称：

```yaml
# config.yaml
source:
  name: "postgresql"
  params:
    host: "windmill-db-1"  # 使用容器服务名称
    port: 5432
    user: "postgres"
    password: "your_password"
    database: "windmill"
```

#### 方案B: 使用Docker网络IP

1. 查找PostgreSQL容器的IP地址：
```bash
docker inspect windmill-db-1 | grep IPAddress
```

2. 在配置中使用该IP地址

#### 方案C: 使用host网络模式

修改 `docker-compose.yml`，让 `db_ops_analyzer` 使用host网络：

```yaml
services:
  db-ops-analyzer:
    network_mode: "host"
    # ... 其他配置
```

然后配置中使用 `localhost` 或主机IP。

### 2. PostgreSQL只监听localhost

**问题**: PostgreSQL配置只监听 `localhost`，外部容器无法连接。

**解决方案**:

1. 进入PostgreSQL容器：
```bash
docker exec -it windmill-db-1 bash
```

2. 检查当前配置：
```bash
psql -U postgres -c "SHOW listen_addresses;"
```

3. 如果显示 `localhost`，需要修改 `postgresql.conf`：
```bash
# 查找配置文件位置
psql -U postgres -c "SHOW config_file;"

# 编辑配置文件（在容器内）
vi /var/lib/postgresql/data/postgresql.conf
```

4. 修改 `listen_addresses`：
```
listen_addresses = '*'  # 监听所有接口
# 或
listen_addresses = '0.0.0.0'  # 监听所有IPv4接口
```

5. 重启PostgreSQL容器：
```bash
docker restart windmill-db-1
```

### 3. pg_hba.conf配置问题

**问题**: PostgreSQL的 `pg_hba.conf` 不允许从该地址连接。

**解决方案**:

1. 检查 `pg_hba.conf`：
```bash
docker exec windmill-db-1 cat /var/lib/postgresql/data/pg_hba.conf
```

2. 添加允许连接的规则：
```
# 允许从Docker网络连接
host    all    all    172.16.0.0/12    md5
# 或允许所有IP（仅用于测试，生产环境不推荐）
host    all    all    0.0.0.0/0    md5
```

3. 重新加载配置：
```bash
docker exec windmill-db-1 psql -U postgres -c "SELECT pg_reload_conf();"
```

### 4. 防火墙问题

**问题**: 防火墙阻止了连接。

**解决方案**:

检查防火墙规则，确保允许PostgreSQL端口（默认5432）的流量。

### 5. 密码错误

**问题**: 用户名或密码不正确。

**解决方案**:

1. 验证密码：
```bash
docker exec -it windmill-db-1 psql -U postgres -d windmill
# 如果提示输入密码，说明密码可能不正确
```

2. 重置密码（如果需要）：
```bash
docker exec -it windmill-db-1 psql -U postgres -c "ALTER USER postgres PASSWORD 'new_password';"
```

## 诊断工具

使用提供的诊断脚本测试连接：

```bash
# 在db_ops_analyzer容器内运行
docker exec -it db-ops-analyzer python /app/scripts/test_postgresql_connection.py \
  --host windmill-db-1 \
  --port 5432 \
  --user postgres \
  --password your_password \
  --database windmill
```

或在主机上运行（如果已安装psycopg2）：

```bash
cd db_ops_analyzer
python scripts/test_postgresql_connection.py \
  --host 10.163.25.156 \
  --port 5432 \
  --user postgres \
  --password your_password \
  --database windmill
```

## 快速检查清单

- [ ] 确认PostgreSQL容器正在运行：`docker ps | grep windmill-db-1`
- [ ] 确认两个容器在同一个Docker网络中：`docker network inspect <network_name>`
- [ ] 检查PostgreSQL监听地址：`docker exec windmill-db-1 psql -U postgres -c "SHOW listen_addresses;"`
- [ ] 检查pg_hba.conf配置：`docker exec windmill-db-1 cat /var/lib/postgresql/data/pg_hba.conf`
- [ ] 测试网络连通性：`docker exec db-ops-analyzer ping windmill-db-1`
- [ ] 使用诊断脚本测试连接

## 推荐的Docker Compose配置

```yaml
services:
  windmill-db:
    image: postgres:17
    container_name: windmill-db-1
    environment:
      POSTGRES_DB: windmill
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: your_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - db_network

  db-ops-analyzer:
    image: db-ops-analyzer:latest
    container_name: db-ops-analyzer
    depends_on:
      - windmill-db
    environment:
      - CONFIG_PATH=/app/config.yaml
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./reports:/app/reports
    networks:
      - db_network

networks:
  db_network:
    driver: bridge

volumes:
  postgres_data:
```

在 `config.yaml` 中使用容器服务名称：

```yaml
source:
  name: "postgresql"
  params:
    host: "windmill-db"  # 使用docker-compose中的服务名称
    port: 5432
    user: "postgres"
    password: "your_password"
    database: "windmill"
```
