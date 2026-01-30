"""PostgreSQL数据源插件"""

import logging
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from db_ops_analyzer.plugins.sources.base import AbstractSource

logger = logging.getLogger(__name__)


class PostgreSQLSource(AbstractSource):
    """PostgreSQL数据源插件"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5432,
                 user: str = "postgres",
                 password: str = "",
                 database: Optional[str] = None,
                 collect_slow_queries: bool = True,
                 collect_processlist: bool = True,
                 collect_status: bool = True,
                 collect_variables: bool = True,
                 collect_indexes: bool = True,
                 collect_tables: bool = True,
                 slow_query_limit: int = 100,
                 # 性能优化参数
                 query_timeout: int = 30,  # 查询超时时间（秒）
                 read_only_mode: bool = True,  # 只读模式
                 table_limit: int = 1000,  # 表信息收集限制
                 index_limit: int = 5000,  # 索引信息收集限制
                 **kwargs):
        """
        初始化PostgreSQL数据源
        
        Args:
            host: PostgreSQL主机地址
            port: PostgreSQL端口
            user: 用户名
            password: 密码
            database: 数据库名（可选，不指定则分析所有数据库）
            collect_slow_queries: 是否收集慢查询
            collect_processlist: 是否收集进程列表
            collect_status: 是否收集状态信息
            collect_variables: 是否收集配置变量
            collect_indexes: 是否收集索引信息
            collect_tables: 是否收集表信息
            slow_query_limit: 慢查询记录数限制
            query_timeout: 查询超时时间（秒）
            read_only_mode: 只读模式
            table_limit: 表信息收集限制
            index_limit: 索引信息收集限制
        """
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database  # PostgreSQL数据库名（可选，None表示使用连接字符串中的数据库）
        self.collect_slow_queries = collect_slow_queries
        self.collect_processlist = collect_processlist
        self.collect_status = collect_status
        self.collect_variables = collect_variables
        self.collect_indexes = collect_indexes
        self.collect_tables = collect_tables
        self.slow_query_limit = slow_query_limit
        self.query_timeout = query_timeout
        self.read_only_mode = read_only_mode
        self.table_limit = table_limit
        self.index_limit = index_limit
        self._connection = None
    
    def _get_connection(self):
        """获取数据库连接（优化：只读模式）"""
        if self._connection is None or self._connection.closed:
            # 构建连接参数
            conn_params = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'cursor_factory': RealDictCursor,
                'connect_timeout': 10
            }
            # 只有当 database 不为 None 时才添加
            if self.database:
                conn_params['database'] = self.database
            
            try:
                self._connection = psycopg2.connect(**conn_params)
            except psycopg2.OperationalError as e:
                error_msg = f"无法连接到PostgreSQL数据库 {self.host}:{self.port}"
                if "could not connect" in str(e).lower() or "connection refused" in str(e).lower():
                    error_msg += f"\n连接被拒绝。可能的原因："
                    error_msg += f"\n1. PostgreSQL服务未运行或未监听该地址"
                    error_msg += f"\n2. 防火墙阻止了连接"
                    error_msg += f"\n3. PostgreSQL配置只允许localhost连接（需要修改postgresql.conf中的listen_addresses）"
                    error_msg += f"\n4. 如果db_ops_analyzer运行在Docker容器中，需要使用容器名称或Docker网络IP，而不是localhost"
                elif "timeout" in str(e).lower():
                    error_msg += f"\n连接超时。可能的原因："
                    error_msg += f"\n1. 网络不通或防火墙阻止"
                    error_msg += f"\n2. 主机地址不正确"
                elif "authentication failed" in str(e).lower() or "password" in str(e).lower():
                    error_msg += f"\n认证失败。请检查用户名和密码是否正确"
                else:
                    error_msg += f"\n错误详情: {str(e)}"
                logger.error(error_msg)
                raise ConnectionError(error_msg) from e
            except Exception as e:
                error_msg = f"连接PostgreSQL数据库时发生未知错误: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise ConnectionError(error_msg) from e
            
            # 设置查询超时（连接级别）
            try:
                with self._connection.cursor() as cursor:
                    cursor.execute(f"SET statement_timeout = '{self.query_timeout * 1000}ms'")
            except Exception as e:
                logger.warning(f"设置查询超时失败: {e}")
            
            logger.info(f"已建立PostgreSQL连接（只读模式: {self.read_only_mode}）")
        return self._connection
    
    def collect(self) -> Dict[str, Any]:
        """收集PostgreSQL数据库信息（已优化：最小化对数据库的影响）"""
        result = {
            'database_type': 'PostgreSQL',
            'host': self.host,
            'port': self.port,
            'database': self.database or 'all',
            'databases': [],  # 所有数据库列表
            'slow_queries': [],
            'processlist': [],
            'status': {},
            'variables': {},
            'indexes': [],
            'tables': [],
            'errors': []
        }
        
        try:
            conn = self._get_connection()
            
            # 首先收集所有数据库列表
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            datname as database_name,
                            pg_database_size(datname) as database_size,
                            (SELECT COUNT(*) FROM pg_stat_database WHERE datname = d.datname) as is_active
                        FROM pg_database d
                        WHERE datistemplate = false
                        ORDER BY pg_database_size(datname) DESC
                    """)
                    rows = cursor.fetchall()
                    result['databases'] = [dict(row) for row in rows]
                    logger.info(f"发现 {len(result['databases'])} 个数据库")
            except Exception as e:
                logger.warning(f"收集数据库列表失败: {e}")
                result['errors'].append(f"数据库列表收集失败: {str(e)}")
            
            # 设置查询超时（连接级别）
            try:
                with conn.cursor() as temp_cursor:
                    temp_cursor.execute(f"SET statement_timeout = '{self.query_timeout * 1000}ms'")
            except Exception as e:
                logger.warning(f"设置查询超时失败: {e}")
            
            # 收集慢查询（从 pg_stat_statements）
            if self.collect_slow_queries:
                try:
                    # 使用独立的连接/事务来避免影响其他查询
                    with conn.cursor() as cursor:
                        # 先检查扩展是否存在
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                            ) as exists
                        """)
                        row = cursor.fetchone()
                        extension_exists = row['exists'] if isinstance(row, dict) else row[0]
                        
                        if extension_exists:
                            cursor.execute("""
                                SELECT 
                                    query,
                                    calls as exec_count,
                                    mean_exec_time / 1000.0 as avg_time_sec,
                                    max_exec_time / 1000.0 as max_time_sec,
                                    total_exec_time / 1000.0 as sum_time_sec
                                FROM pg_stat_statements
                                WHERE mean_exec_time > 0
                                ORDER BY total_exec_time DESC
                                LIMIT %s
                            """, (self.slow_query_limit,))
                            rows = cursor.fetchall()
                            result['slow_queries'] = [dict(row) for row in rows]
                            logger.info(f"收集到 {len(result['slow_queries'])} 条慢查询")
                        else:
                            logger.info("pg_stat_statements扩展未启用，跳过慢查询收集")
                            result['errors'].append("慢查询收集跳过: pg_stat_statements扩展未启用")
                except Exception as e:
                    logger.warning(f"收集慢查询失败: {e}")
                    result['errors'].append(f"慢查询收集失败: {str(e)}")
                    # 如果事务失败，回滚并继续
                    try:
                        conn.rollback()
                    except:
                        pass
            
            # 收集进程列表
            if self.collect_processlist:
                try:
                    # 确保使用新的cursor，避免事务问题
                    with conn.cursor() as cursor:
                        if self.database:
                            cursor.execute("""
                                SELECT 
                                    pid,
                                    usename,
                                    application_name,
                                    client_addr,
                                    state,
                                    query,
                                    query_start,
                                    state_change
                                FROM pg_stat_activity
                                WHERE datname = %s
                            """, (self.database,))
                        else:
                            cursor.execute("""
                                SELECT 
                                    pid,
                                    usename,
                                    application_name,
                                    client_addr,
                                    state,
                                    query,
                                    query_start,
                                    state_change
                                FROM pg_stat_activity
                                WHERE datname IS NOT NULL
                            """)
                        rows = cursor.fetchall()
                        result['processlist'] = [dict(row) for row in rows]
                        logger.info(f"收集到 {len(result['processlist'])} 个进程")
                except Exception as e:
                    logger.warning(f"收集进程列表失败: {e}")
                    result['errors'].append(f"进程列表收集失败: {str(e)}")
                    try:
                        conn.rollback()
                    except:
                        pass
            
            # 收集状态信息
            if self.collect_status:
                try:
                    # 使用独立的cursor避免事务问题
                    with conn.cursor() as cursor:
                        # 数据库统计信息
                        if self.database:
                            cursor.execute("""
                                SELECT 
                                    numbackends as connections,
                                    xact_commit as commits,
                                    xact_rollback as rollbacks,
                                    blks_read as disk_reads,
                                    blks_hit as cache_hits,
                                    tup_returned as tuples_returned,
                                    tup_fetched as tuples_fetched,
                                    tup_inserted as tuples_inserted,
                                    tup_updated as tuples_updated,
                                    tup_deleted as tuples_deleted
                                FROM pg_stat_database
                                WHERE datname = %s
                            """, (self.database,))
                        else:
                            # 如果没有指定数据库，收集所有数据库的汇总信息
                            cursor.execute("""
                                SELECT 
                                    SUM(numbackends) as connections,
                                    SUM(xact_commit) as commits,
                                    SUM(xact_rollback) as rollbacks,
                                    SUM(blks_read) as disk_reads,
                                    SUM(blks_hit) as cache_hits,
                                    SUM(tup_returned) as tuples_returned,
                                    SUM(tup_fetched) as tuples_fetched,
                                    SUM(tup_inserted) as tuples_inserted,
                                    SUM(tup_updated) as tuples_updated,
                                    SUM(tup_deleted) as tuples_deleted
                                FROM pg_stat_database
                                WHERE datname NOT IN ('template0', 'template1')
                            """)
                        row = cursor.fetchone()
                        if row:
                            result['status'] = dict(row)
                        
                        logger.info(f"收集到数据库状态信息")
                except Exception as e:
                    logger.warning(f"收集状态信息失败: {e}")
                    result['errors'].append(f"状态信息收集失败: {str(e)}")
                    try:
                        conn.rollback()
                    except:
                        pass
            
            # 收集配置变量（优化：只收集重要的配置，减少数据量）
            if self.collect_variables:
                try:
                    with conn.cursor() as cursor:
                        # 只收集重要的配置变量，过滤掉默认值和不重要的配置
                        cursor.execute("""
                            SELECT name, setting, unit, context
                            FROM pg_settings
                            WHERE context IN ('postmaster', 'sighup', 'superuser', 'user')
                            AND (
                                name LIKE '%timeout%' OR
                                name LIKE '%memory%' OR
                                name LIKE '%cache%' OR
                                name LIKE '%connection%' OR
                                name LIKE '%log%' OR
                                name LIKE '%wal%' OR
                                name LIKE '%checkpoint%' OR
                                name LIKE '%shared_buffers%' OR
                                name LIKE '%work_mem%' OR
                                name LIKE '%maintenance_work_mem%' OR
                                name LIKE '%max_connections%' OR
                                name LIKE '%listen_addresses%'
                            )
                            ORDER BY name
                        """)
                        rows = cursor.fetchall()
                        result['variables'] = {row['name']: {
                            'value': row['setting'],
                            'unit': row['unit'],
                            'context': row['context']
                        } for row in rows}
                        logger.info(f"收集到 {len(result['variables'])} 个重要配置变量（已过滤）")
                except Exception as e:
                    logger.warning(f"收集配置变量失败: {e}")
                    result['errors'].append(f"配置变量收集失败: {str(e)}")
                    try:
                        conn.rollback()
                    except:
                        pass
            
            # 收集索引信息（优化：只收集基本信息，不收集完整的indexdef）
            if self.collect_indexes:
                try:
                    with conn.cursor() as cursor:
                        # 优化：先选择indexdef，然后在Python中判断类型
                        cursor.execute("""
                            SELECT 
                                schemaname,
                                tablename,
                                indexname,
                                indexdef
                            FROM pg_indexes
                            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                            ORDER BY schemaname, tablename, indexname
                            LIMIT %s
                        """, (self.index_limit,))
                        rows = cursor.fetchall()
                        # 在Python中判断索引类型，避免SQL中的字段引用问题
                        indexes_list = []
                        for row in rows:
                            row_dict = dict(row)
                            indexdef = row_dict.get('indexdef', '')
                            if 'PRIMARY KEY' in indexdef:
                                index_type = 'PRIMARY KEY'
                            elif 'UNIQUE' in indexdef:
                                index_type = 'UNIQUE'
                            else:
                                index_type = 'INDEX'
                            indexes_list.append({
                                'schemaname': row_dict.get('schemaname'),
                                'tablename': row_dict.get('tablename'),
                                'indexname': row_dict.get('indexname'),
                                'index_type': index_type
                            })
                        result['indexes'] = indexes_list
                        logger.info(f"收集到 {len(result['indexes'])} 条索引信息（限制: {self.index_limit}）")
                except Exception as e:
                    logger.warning(f"收集索引信息失败: {e}")
                    result['errors'].append(f"索引信息收集失败: {str(e)}")
                    try:
                        conn.rollback()
                    except:
                        pass
            
            # 收集表信息
            if self.collect_tables:
                try:
                    # 如果指定了数据库，只收集该数据库的表
                    # 如果没有指定，收集当前连接数据库的表（通常是postgres）
                    target_db = self.database or conn.info.dbname
                    
                    with conn.cursor() as cursor:
                        # 使用pg_class和pg_namespace获取所有表（最可靠的方法）
                        # 添加数据库名信息
                        cursor.execute("""
                            SELECT 
                                %s as database_name,
                                nsp.nspname as schemaname,
                                cls.relname as tablename,
                                COALESCE(stat.n_live_tup, 0) as table_rows,
                                COALESCE(pg_total_relation_size(cls.oid), 0) as total_size,
                                COALESCE(pg_relation_size(cls.oid), 0) as data_size,
                                COALESCE(pg_indexes_size(cls.oid), 0) as index_size
                            FROM pg_class cls
                            JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
                            LEFT JOIN pg_stat_user_tables stat 
                                ON stat.schemaname = nsp.nspname 
                                AND stat.relname = cls.relname
                            WHERE cls.relkind = 'r'  -- 只获取普通表
                            AND nsp.nspname NOT IN ('pg_catalog', 'information_schema')
                            ORDER BY 
                                CASE WHEN COALESCE(stat.n_live_tup, 0) > 0 OR pg_total_relation_size(cls.oid) > 1048576 THEN 0 ELSE 1 END,
                                pg_total_relation_size(cls.oid) DESC
                            LIMIT %s
                        """, (target_db, self.table_limit))
                        rows = cursor.fetchall()
                        result['tables'] = [dict(row) for row in rows]
                        logger.info(f"从数据库 '{target_db}' 收集到 {len(result['tables'])} 个表信息（限制: {self.table_limit}）")
                        
                        # 如果没有指定数据库，尝试收集其他数据库的表信息（最多3个最大的数据库）
                        if not self.database and len(result['databases']) > 1:
                            # 获取其他数据库的表（排除当前数据库）
                            other_dbs = [db['database_name'] for db in result['databases'] 
                                       if db['database_name'] != target_db 
                                       and db['database_name'] not in ['template0', 'template1']][:3]
                            
                            for db_name in other_dbs:
                                try:
                                    # 连接到其他数据库收集表信息
                                    other_conn = psycopg2.connect(
                                        host=self.host,
                                        port=self.port,
                                        user=self.user,
                                        password=self.password,
                                        database=db_name,
                                        cursor_factory=RealDictCursor,
                                        connect_timeout=5
                                    )
                                    with other_conn.cursor() as other_cursor:
                                        other_cursor.execute("""
                                            SELECT 
                                                %s as database_name,
                                                nsp.nspname as schemaname,
                                                cls.relname as tablename,
                                                COALESCE(stat.n_live_tup, 0) as table_rows,
                                                COALESCE(pg_total_relation_size(cls.oid), 0) as total_size,
                                                COALESCE(pg_relation_size(cls.oid), 0) as data_size,
                                                COALESCE(pg_indexes_size(cls.oid), 0) as index_size
                                            FROM pg_class cls
                                            JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
                                            LEFT JOIN pg_stat_user_tables stat 
                                                ON stat.schemaname = nsp.nspname 
                                                AND stat.relname = cls.relname
                                            WHERE cls.relkind = 'r'
                                            AND nsp.nspname NOT IN ('pg_catalog', 'information_schema')
                                            ORDER BY pg_total_relation_size(cls.oid) DESC
                                            LIMIT %s
                                        """, (db_name, min(50, self.table_limit // len(other_dbs))))
                                        other_rows = other_cursor.fetchall()
                                        result['tables'].extend([dict(row) for row in other_rows])
                                        logger.info(f"从数据库 '{db_name}' 收集到 {len(other_rows)} 个表信息")
                                    other_conn.close()
                                except Exception as e:
                                    logger.warning(f"收集数据库 '{db_name}' 的表信息失败: {e}")
                                    result['errors'].append(f"数据库 '{db_name}' 表信息收集失败: {str(e)}")
                except Exception as e:
                    logger.warning(f"收集表信息失败: {e}")
                    result['errors'].append(f"表信息收集失败: {str(e)}")
                    try:
                        conn.rollback()
                    except:
                        pass
            
        except ConnectionError as e:
            # 连接错误，直接抛出，不要继续收集
            logger.error(f"PostgreSQL连接失败: {e}")
            raise
        except Exception as e:
            logger.error(f"收集PostgreSQL数据失败: {e}", exc_info=True)
            result['errors'].append(f"数据收集失败: {str(e)}")
        finally:
            if self._connection and not self._connection.closed:
                self._connection.close()
                self._connection = None
        
        return result
    
    def validate(self) -> bool:
        """验证配置"""
        try:
            conn = self._get_connection()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"PostgreSQL连接验证失败: {e}")
            return False
