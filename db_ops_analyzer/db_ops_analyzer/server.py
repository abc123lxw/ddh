"""FastAPI服务器"""

import hmac
import hashlib
import logging
import time
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Body, Query, Cookie, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from pathlib import Path

from db_ops_analyzer.config import Config
from db_ops_analyzer.task import TaskExecutor

# 登录账号密码（可后续改为配置/环境变量）
LOGIN_USERNAME = "admin"
LOGIN_PASSWORD = "ddh2025"
SESSION_COOKIE_NAME = "session"
SESSION_SECRET = "ddh-ops-analyzer-session-secret-change-in-prod"
SESSION_MAX_AGE = 86400  # 24 小时

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局配置和执行器
config = None
executor = None

app = FastAPI(title="数据库运维分析工具", version="0.1.0")

# 静态文件服务
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    # 挂载静态文件到 /ui/static
    app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="static")
    # 同时挂载到 /static 以兼容前端代码
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static_legacy")


def _sign_session(username: str) -> str:
    expiry = int(time.time()) + SESSION_MAX_AGE
    payload = f"{username}:{expiry}"
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_session(cookie_val: Optional[str]) -> Optional[str]:
    if not cookie_val:
        return None
    parts = cookie_val.split(":")
    # format: username:expiry:signature
    if len(parts) < 3:
        return None
    try:
        username, expiry_str, sig = parts[0], parts[1], ":".join(parts[2:])
        expiry = int(expiry_str)
        if expiry <= time.time():
            return None
        payload = f"{username}:{expiry_str}"
        expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, sig):
            return username
    except (ValueError, IndexError):
        pass
    return None


def require_auth(session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)) -> str:
    """依赖：校验 session cookie，未登录则 401"""
    user = _verify_session(session)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user


# 数据库连接弱口令校验（符合网安要求：不允许使用弱口令连接数据库，避免告警）
WEAK_PASSWORDS = frozenset({
    "123456", "12345678", "123456789", "1234567890", "password", "root", "admin",
    "111111", "000000", "qwerty", "abc123", "admin123", "root123", "password123",
    "123123", "654321", "888888", "666666", "admin888", "root888", "test", "test123",
})
MIN_DB_PASSWORD_LENGTH = 8


def is_weak_db_password(password: Optional[str]) -> bool:
    """判断数据库密码是否为弱口令。空密码不校验（由必填逻辑处理）。"""
    if not password or not password.strip():
        return False
    p = password.strip()
    if len(p) < MIN_DB_PASSWORD_LENGTH:
        return True
    if p.lower() in WEAK_PASSWORDS:
        return True
    # 纯数字或纯字母视为弱
    if p.isdigit() or p.isalpha():
        return True
    return False


# 登录请求
class LoginRequest(BaseModel):
    username: str
    password: str


# 请求模型
class DatabaseConfig(BaseModel):
    """数据库连接配置（支持多种数据库类型）"""
    db_type: Optional[str] = "mysql"  # 数据库类型：mysql, postgresql, redis, mongodb
    host: str
    port: int = 3306
    user: Optional[str] = None  # Redis 不需要用户名
    password: Optional[str] = None  # Redis 和 MongoDB 可能不需要密码
    database: Optional[str] = None  # Redis 前端可能传数字 0，由 validator 转为 str
    auth_source: Optional[str] = None  # MongoDB 认证数据库

    @field_validator("database", mode="before")
    @classmethod
    def coerce_database(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)  # 兼容前端传 0（Redis db 编号）
    
    # MySQL/PostgreSQL 通用选项
    collect_slow_queries: bool = True
    collect_processlist: bool = True
    collect_status: bool = True
    collect_variables: bool = True
    collect_indexes: bool = True
    collect_tables: bool = True
    slow_query_limit: int = 100
    query_timeout: int = 30
    read_only_mode: bool = True
    low_priority: bool = True  # 仅 MySQL
    table_limit: int = 1000
    index_limit: int = 5000
    
    # Redis 特定选项
    collect_info: Optional[bool] = None
    collect_slowlog: Optional[bool] = None
    collect_clients: Optional[bool] = None
    collect_memory: Optional[bool] = None
    collect_keyspace: Optional[bool] = None
    collect_config: Optional[bool] = None
    slowlog_limit: Optional[int] = None
    socket_timeout: Optional[int] = None
    
    # MongoDB 特定选项
    collect_server_status: Optional[bool] = None
    collect_database_stats: Optional[bool] = None
    collect_collection_stats: Optional[bool] = None
    collect_operations: Optional[bool] = None
    collect_connections: Optional[bool] = None
    collection_limit: Optional[int] = None
    socket_timeout_ms: Optional[int] = None


@app.on_event("startup")
async def startup():
    """启动时初始化"""
    global config, executor
    try:
        config = Config()
        executor = TaskExecutor(config)
        logger.info("数据库运维分析工具启动成功")
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        raise


@app.get("/")
async def root():
    """根路径 - 拒绝访问"""
    raise HTTPException(status_code=404, detail="Not Found")


@app.post("/api/login")
async def login(req: LoginRequest):
    """登录：账号 admin，密码 ddh2025"""
    if req.username != LOGIN_USERNAME or req.password != LOGIN_PASSWORD:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = _sign_session(req.username)
    response = JSONResponse(content={"ok": True, "user": req.username})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/api/auth/check")
async def auth_check(session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)):
    """检查是否已登录"""
    user = _verify_session(session)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return {"user": user}


@app.post("/api/logout")
async def logout():
    """登出：清除 session"""
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/ui/")
async def ui_root():
    """UI首页 - 返回登录/主应用页面，前端根据 /api/auth/check 决定显示登录或主界面"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="前端页面不存在")


@app.get("/health")
async def health():
    """健康检查（不校验登录）"""
    return {"status": "ok", "service": "db-ops-analyzer"}


@app.post("/api/test-connection", dependencies=[Depends(require_auth)])
async def test_connection(
    db_config: DatabaseConfig = Body(..., description="数据库连接配置")
) -> Dict[str, Any]:
    """测试数据库连接（仅测试连接，不执行数据收集）"""
    try:
        db_type = db_config.db_type or "mysql"
        
        # 验证必填字段
        if not db_config.host:
            raise ValueError("数据库连接信息不完整：需要提供主机地址")
        
        # MySQL 和 PostgreSQL 需要用户名和密码
        if db_type in ['mysql', 'postgresql']:
            if not db_config.user:
                raise ValueError("数据库连接信息不完整：需要提供用户名")
            if not db_config.password:
                raise ValueError("数据库连接信息不完整：需要提供密码")
            if is_weak_db_password(db_config.password):
                raise HTTPException(
                    status_code=400,
                    detail="为符合安全策略，不允许使用弱口令连接数据库（密码至少8位且需包含字母与数字，且不能为常见弱口令）。若无法修改数据库密码，可联系网安做白名单或使用其他合规方式。"
                )
        # Redis / MongoDB 若填写了密码则也做弱口令校验
        if db_type in ['redis', 'mongodb'] and db_config.password:
            if is_weak_db_password(db_config.password):
                raise HTTPException(
                    status_code=400,
                    detail="为符合安全策略，不允许使用弱口令连接数据库（密码至少8位且需包含字母与数字，且不能为常见弱口令）。若无法修改数据库密码，可联系网安做白名单或使用其他合规方式。"
                )
        
        # 根据数据库类型测试连接
        if db_type == 'postgresql':
            from db_ops_analyzer.plugins.sources.postgresql import PostgreSQLSource
            source = PostgreSQLSource(
                host=db_config.host,
                port=db_config.port or 5432,
                user=db_config.user or "",
                password=db_config.password or "",
                database=db_config.database,
                collect_slow_queries=False,  # 测试连接时不收集数据
                collect_processlist=False,
                collect_status=False,
                collect_variables=False,
                collect_indexes=False,
                collect_tables=False
            )
            # 测试连接
            conn = source._get_connection()
            # 执行一个简单查询验证连接
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                row = cursor.fetchone()
                # RealDictCursor 返回字典，使用 'version' 键或获取第一个值
                if isinstance(row, dict):
                    version = row.get('version', list(row.values())[0] if row else None)
                else:
                    version = row[0] if row else None
            conn.close()
            version_str = str(version) if version else "Unknown"
            return {
                "status": "success",
                "message": "连接成功",
                "database_type": "PostgreSQL",
                "version": version_str.split(',')[0] if version_str != "Unknown" else "Unknown"
            }
        
        elif db_type == 'mysql':
            from db_ops_analyzer.plugins.sources.mysql import MySQLSource
            source = MySQLSource(
                host=db_config.host,
                port=db_config.port or 3306,
                user=db_config.user or "",
                password=db_config.password or "",
                database=db_config.database,
                collect_slow_queries=False,
                collect_processlist=False,
                collect_status=False,
                collect_variables=False,
                collect_indexes=False,
                collect_tables=False
            )
            # 测试连接
            conn = source._get_connection()
            # 执行一个简单查询验证连接
            with conn.cursor() as cursor:
                cursor.execute("SELECT VERSION() as version;")
                row = cursor.fetchone()
                # DictCursor 返回字典，使用 'version' 键或获取第一个值
                if isinstance(row, dict):
                    version = row.get('version', list(row.values())[0] if row else None)
                else:
                    version = row[0] if row else None
            conn.close()
            return {
                "status": "success",
                "message": "连接成功",
                "database_type": "MySQL",
                "version": str(version) if version else "Unknown"
            }
        
        elif db_type == 'redis':
            from db_ops_analyzer.plugins.sources.redis import RedisSource
            source = RedisSource(
                host=db_config.host,
                port=db_config.port or 6379,
                password=db_config.password,
                database=int(db_config.database) if db_config.database else 0,
                collect_info=False,
                collect_slowlog=False,
                collect_clients=False,
                collect_memory=False,
                collect_keyspace=False,
                collect_config=False
            )
            # 测试连接
            client = source._get_client()
            # 执行PING命令验证连接
            result = client.ping()
            client.close()
            if result:
                return {
                    "status": "success",
                    "message": "连接成功",
                    "database_type": "Redis"
                }
            else:
                raise ConnectionError("Redis连接失败：PING命令未返回预期结果")
        
        elif db_type == 'mongodb':
            from db_ops_analyzer.plugins.sources.mongodb import MongoDBSource
            source = MongoDBSource(
                host=db_config.host,
                port=db_config.port or 27017,
                user=db_config.user,
                password=db_config.password,
                database=db_config.database,
                auth_source=db_config.auth_source,
                collect_server_status=False,
                collect_database_stats=False,
                collect_collection_stats=False,
                collect_indexes=False,
                collect_operations=False,
                collect_connections=False
            )
            # 测试连接
            client = source._get_client()
            # 执行ping命令验证连接
            result = client.admin.command('ping')
            # 获取版本信息
            try:
                server_info = client.server_info()
                version = server_info.get('version', 'Unknown')
            except Exception as e:
                logger.warning(f"获取MongoDB版本信息失败: {e}")
                version = "Unknown"
            client.close()
            return {
                "status": "success",
                "message": "连接成功",
                "database_type": "MongoDB",
                "version": str(version) if version else "Unknown"
            }
        
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")
    
    except ConnectionError as e:
        # 连接错误，返回详细错误信息
        error_msg = str(e)
        return {
            "status": "failed",
            "message": "连接失败",
            "error": error_msg,
            "database_type": db_config.db_type or "unknown"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"测试连接失败: {e}", exc_info=True)
        error_msg = str(e)
        # 尝试提取更友好的错误信息
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            error_msg = f"连接超时。可能的原因：\n1. 网络不通或防火墙阻止\n2. 主机地址或端口不正确\n3. 数据库服务未运行\n\n原始错误: {error_msg}"
        elif "connection refused" in error_msg.lower() or "could not connect" in error_msg.lower():
            error_msg = f"连接被拒绝。可能的原因：\n1. 数据库服务未运行\n2. 防火墙阻止了连接\n3. 数据库配置只允许特定IP连接\n\n原始错误: {error_msg}"
        elif "authentication failed" in error_msg.lower() or "password" in error_msg.lower():
            error_msg = f"认证失败。请检查用户名和密码是否正确\n\n原始错误: {error_msg}"
        
        return {
            "status": "failed",
            "message": "连接失败",
            "error": error_msg,
            "database_type": db_config.db_type or "unknown"
        }


def _connection_summary_from_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """从任务配置提取连接摘要（不含账号密码），供页面展示"""
    source = task.get("source") or {}
    params = source.get("params") or {}
    db_type = (source.get("name") or "mysql").lower()
    return {
        "db_type": db_type,
        "host": params.get("host") or "",
        "port": params.get("port") or (3306 if db_type == "mysql" else 5432 if db_type == "postgresql" else 6379 if db_type == "redis" else 27017),
        "database": params.get("database") or "",
    }


@app.get("/api/tasks", dependencies=[Depends(require_auth)])
async def get_tasks() -> Dict[str, Any]:
    """获取所有任务及连接摘要（不含密码），便于仅用 config 时在页面展示"""
    tasks = config.get_tasks()
    return {
        "tasks": [
            {
                "name": task.get("name"),
                "description": task.get("description", ""),
                "connection_summary": _connection_summary_from_task(task),
            }
            for task in tasks
        ]
    }


def _test_connection_with_params(db_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """使用参数字典测试连接（供 config 测试用），不校验弱口令"""
    db_type = (db_type or "mysql").lower()
    host = params.get("host") or "localhost"
    port = int(params.get("port") or (3306 if db_type == "mysql" else 5432 if db_type == "postgresql" else 6379 if db_type == "redis" else 27017))
    user = params.get("user") or ""
    password = params.get("password") or ""
    database = params.get("database")
    auth_source = params.get("auth_source")

    if db_type == "postgresql":
        from db_ops_analyzer.plugins.sources.postgresql import PostgreSQLSource
        source = PostgreSQLSource(
            host=host, port=port, user=user, password=password, database=database,
            collect_slow_queries=False, collect_processlist=False, collect_status=False,
            collect_variables=False, collect_indexes=False, collect_tables=False
        )
        conn = source._get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            row = cursor.fetchone()
            version = row.get("version", list(row.values())[0] if row else None) if isinstance(row, dict) else (row[0] if row else None)
        conn.close()
        version_str = str(version) if version else "Unknown"
        return {"status": "success", "message": "连接成功", "database_type": "PostgreSQL", "version": version_str.split(",")[0] if version_str != "Unknown" else "Unknown"}

    if db_type == "mysql":
        from db_ops_analyzer.plugins.sources.mysql import MySQLSource
        source = MySQLSource(
            host=host, port=port, user=user, password=password, database=database,
            collect_slow_queries=False, collect_processlist=False, collect_status=False,
            collect_variables=False, collect_indexes=False, collect_tables=False
        )
        conn = source._get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() as version;")
            row = cursor.fetchone()
            version = row.get("version", list(row.values())[0] if row else None) if isinstance(row, dict) else (row[0] if row else None)
        conn.close()
        return {"status": "success", "message": "连接成功", "database_type": "MySQL", "version": str(version) if version else "Unknown"}

    if db_type == "redis":
        from db_ops_analyzer.plugins.sources.redis import RedisSource
        db_num = int(params.get("database", 0)) if params.get("database") is not None else 0
        source = RedisSource(host=host, port=port, password=password or None, database=db_num, collect_info=False, collect_slowlog=False, collect_clients=False, collect_memory=False, collect_keyspace=False, collect_config=False)
        client = source._get_client()
        result = client.ping()
        client.close()
        if result:
            return {"status": "success", "message": "连接成功", "database_type": "Redis"}
        raise ConnectionError("Redis连接失败：PING未返回预期结果")

    if db_type == "mongodb":
        from db_ops_analyzer.plugins.sources.mongodb import MongoDBSource
        source = MongoDBSource(host=host, port=port, user=user, password=password, database=database, auth_source=auth_source, collect_server_status=False, collect_database_stats=False, collect_collection_stats=False, collect_indexes=False, collect_operations=False, collect_connections=False)
        client = source._get_client()
        client.admin.command("ping")
        try:
            version = client.server_info().get("version", "Unknown")
        except Exception:
            version = "Unknown"
        client.close()
        return {"status": "success", "message": "连接成功", "database_type": "MongoDB", "version": str(version)}

    raise ValueError(f"不支持的数据库类型: {db_type}")


@app.post("/api/tasks/{task_name}/test-connection", dependencies=[Depends(require_auth)])
async def test_connection_by_task(task_name: str) -> Dict[str, Any]:
    """使用 config.yaml 中该任务的配置测试连接（不传账号密码，无网安问题）"""
    task_config = config.get_task(task_name)
    if not task_config:
        raise HTTPException(status_code=404, detail="任务不存在")
    source = task_config.get("source") or {}
    params = source.get("params") or {}
    db_type = (source.get("name") or "mysql").lower()
    try:
        return _test_connection_with_params(db_type, params)
    except ConnectionError as e:
        return {"status": "failed", "message": "连接失败", "error": str(e), "database_type": db_type}
    except Exception as e:
        logger.error(f"测试连接失败: {e}", exc_info=True)
        return {"status": "failed", "message": "连接失败", "error": str(e), "database_type": db_type}


@app.post("/api/tasks/{task_name}/run", dependencies=[Depends(require_auth)])
async def run_task(
    task_name: str,
    db_config: Optional[DatabaseConfig] = Body(None, description="数据库配置（可选，不提供则使用配置文件）")
) -> Dict[str, Any]:
    """执行任务，支持动态配置覆盖"""
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    try:
        # 获取基础任务配置
        task_config = config.get_task(task_name)
        if not task_config:
            raise ValueError(f"任务不存在: {task_name}")
        
        # 如果提供了动态配置，则覆盖
        if db_config:
            # 验证必填字段（Redis 和 MongoDB 可能不需要用户名和密码）
            db_type = db_config.db_type or "mysql"
            if not db_config.host:
                raise ValueError("数据库连接信息不完整：需要提供主机地址")
            
            # MySQL 和 PostgreSQL 需要用户名和密码
            if db_type in ['mysql', 'postgresql']:
                if not db_config.user:
                    raise ValueError("数据库连接信息不完整：需要提供用户名")
                if not db_config.password:
                    raise ValueError("数据库连接信息不完整：需要提供密码")
            
            # MongoDB 如果提供了用户名，则需要密码
            if db_type == 'mongodb' and db_config.user and not db_config.password:
                raise ValueError("数据库连接信息不完整：如果提供了用户名，则必须提供密码")
            
            # 弱口令校验（符合网安要求）
            if db_type in ['mysql', 'postgresql'] and db_config.password and is_weak_db_password(db_config.password):
                raise HTTPException(
                    status_code=400,
                    detail="为符合安全策略，不允许使用弱口令连接数据库（密码至少8位且需包含字母与数字，且不能为常见弱口令）。若无法修改数据库密码，可联系网安做白名单或使用其他合规方式。"
                )
            if db_type in ['redis', 'mongodb'] and db_config.password and is_weak_db_password(db_config.password):
                raise HTTPException(
                    status_code=400,
                    detail="为符合安全策略，不允许使用弱口令连接数据库（密码至少8位且需包含字母与数字，且不能为常见弱口令）。若无法修改数据库密码，可联系网安做白名单或使用其他合规方式。"
                )
            
            import copy
            temp_config = copy.deepcopy(task_config)
            
            # 设置 source 类型
            if 'source' not in temp_config:
                temp_config['source'] = {}
            temp_config['source']['name'] = db_type
            
            # 覆盖 source 配置
            if 'params' not in temp_config['source']:
                temp_config['source']['params'] = {}
            source_params = temp_config['source']['params']
            
            # 通用连接信息
            source_params['host'] = db_config.host
            source_params['port'] = db_config.port
            # 密码可能为空（Redis/MongoDB）
            if db_config.password:
                source_params['password'] = db_config.password
            if db_config.database:
                source_params['database'] = db_config.database
            
            # MySQL/PostgreSQL 配置
            if db_type in ['mysql', 'postgresql']:
                if db_config.user:
                    source_params['user'] = db_config.user
                source_params['collect_slow_queries'] = db_config.collect_slow_queries
                source_params['collect_processlist'] = db_config.collect_processlist
                source_params['collect_status'] = db_config.collect_status
                source_params['collect_variables'] = db_config.collect_variables
                source_params['collect_indexes'] = db_config.collect_indexes
                source_params['collect_tables'] = db_config.collect_tables
                source_params['slow_query_limit'] = db_config.slow_query_limit
                source_params['query_timeout'] = db_config.query_timeout
                source_params['read_only_mode'] = db_config.read_only_mode
                source_params['table_limit'] = db_config.table_limit
                source_params['index_limit'] = db_config.index_limit
                if db_type == 'mysql':
                    source_params['low_priority'] = db_config.low_priority
            
            # Redis 配置
            elif db_type == 'redis':
                if db_config.user:
                    source_params['user'] = db_config.user
                source_params['collect_info'] = db_config.collect_info if db_config.collect_info is not None else db_config.collect_status
                source_params['collect_slowlog'] = db_config.collect_slowlog if db_config.collect_slowlog is not None else db_config.collect_slow_queries
                source_params['collect_clients'] = db_config.collect_clients if db_config.collect_clients is not None else db_config.collect_processlist
                source_params['collect_memory'] = db_config.collect_memory if db_config.collect_memory is not None else db_config.collect_status
                source_params['collect_keyspace'] = db_config.collect_keyspace if db_config.collect_keyspace is not None else db_config.collect_tables
                source_params['collect_config'] = db_config.collect_config if db_config.collect_config is not None else db_config.collect_variables
                source_params['slowlog_limit'] = db_config.slowlog_limit if db_config.slowlog_limit is not None else db_config.slow_query_limit
                source_params['socket_timeout'] = db_config.socket_timeout if db_config.socket_timeout is not None else db_config.query_timeout
                # Redis database 是数字（0-15）
                if db_config.database:
                    try:
                        source_params['database'] = int(db_config.database)
                    except:
                        source_params['database'] = 0
            
            # MongoDB 配置
            elif db_type == 'mongodb':
                if db_config.user:
                    source_params['user'] = db_config.user
                if db_config.auth_source:
                    source_params['auth_source'] = db_config.auth_source
                source_params['collect_server_status'] = db_config.collect_server_status if db_config.collect_server_status is not None else db_config.collect_status
                source_params['collect_database_stats'] = db_config.collect_database_stats if db_config.collect_database_stats is not None else db_config.collect_tables
                source_params['collect_collection_stats'] = db_config.collect_collection_stats if db_config.collect_collection_stats is not None else db_config.collect_tables
                source_params['collect_indexes'] = db_config.collect_indexes
                source_params['collect_operations'] = db_config.collect_operations if db_config.collect_operations is not None else db_config.collect_status
                source_params['collect_connections'] = db_config.collect_connections if db_config.collect_connections is not None else db_config.collect_processlist
                source_params['collection_limit'] = db_config.collection_limit if db_config.collection_limit is not None else db_config.table_limit
                source_params['index_limit'] = db_config.index_limit
                source_params['socket_timeout_ms'] = db_config.socket_timeout_ms if db_config.socket_timeout_ms is not None else (db_config.query_timeout * 1000)
            
            run_id = executor.execute_task_async(task_name, override_config=temp_config)
        else:
            # 使用配置文件（config.yaml）：不做弱口令校验，便于内网/无法改库密时通过 config 执行
            run_id = executor.execute_task_async(task_name)
        
        return {
            "run_id": run_id,
            "task_name": task_name,
            "status": "started",
            "config_source": "dynamic" if db_config else "file"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"执行任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}", dependencies=[Depends(require_auth)])
async def get_run(run_id: int) -> Dict[str, Any]:
    """获取运行信息"""
    run = executor.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return run


@app.get("/api/reports", dependencies=[Depends(require_auth)])
async def list_reports(
    database: Optional[str] = Query(None, alias="database"),
    start_time: Optional[str] = Query(None, alias="start_time"),
    end_time: Optional[str] = Query(None, alias="end_time"),
    limit: Optional[int] = Query(10, alias="limit")
) -> Dict[str, Any]:
    """列出报告"""
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    reports = executor.list_reports(
        database=database,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
    
    return {"reports": reports}


@app.get("/api/reports/{report_id}", dependencies=[Depends(require_auth)])
async def get_report(report_id: str):
    """获取报告内容（返回Markdown文本）"""
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    report = executor.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 返回报告内容（Markdown格式）
    from fastapi.responses import Response
    return Response(
        content=report.get('content', ''),
        media_type="text/markdown; charset=utf-8"
    )


if __name__ == "__main__":
    import uvicorn
    import os
    # 优先使用环境变量，然后是配置文件
    if config:
        server_config = config.server
    else:
        # 如果config未初始化，从环境变量或默认值读取
        server_config = {
            "host": os.getenv("SERVER_HOST", "0.0.0.0"),
            "port": int(os.getenv("SERVER_PORT", "8000"))
        }
    uvicorn.run(app, host=server_config["host"], port=server_config["port"])
