"""MySQL数据源插件"""

import logging
import json
from typing import Dict, Any, List, Optional
import pymysql
from pymysql.cursors import DictCursor
from db_ops_analyzer.plugins.sources.base import AbstractSource

logger = logging.getLogger(__name__)


class MySQLSource(AbstractSource):
    """MySQL数据源插件"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 3306,
                 user: str = "root",
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
                 max_connections: int = 1,  # 最大连接数（限制为1，避免占用过多连接）
                 read_only_mode: bool = True,  # 只读模式
                 low_priority: bool = True,  # 低优先级查询
                 table_limit: int = 1000,  # 表信息收集限制
                 index_limit: int = 5000,  # 索引信息收集限制
                 **kwargs):
        """
        初始化MySQL数据源
        
        Args:
            host: MySQL主机地址
            port: MySQL端口
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
        """
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.collect_slow_queries = collect_slow_queries
        self.collect_processlist = collect_processlist
        self.collect_status = collect_status
        self.collect_variables = collect_variables
        self.collect_indexes = collect_indexes
        self.collect_tables = collect_tables
        self.slow_query_limit = slow_query_limit
        # 性能优化参数
        self.query_timeout = query_timeout
        self.max_connections = max_connections
        self.read_only_mode = read_only_mode
        self.low_priority = low_priority
        self.table_limit = table_limit
        self.index_limit = index_limit
        self._connection = None
    
    def _get_connection(self):
        """获取数据库连接（优化：只读模式、低优先级）"""
        if self._connection is None or not self._connection.open:
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                cursorclass=DictCursor,
                charset='utf8mb4',
                read_timeout=self.query_timeout,  # 读取超时
                write_timeout=self.query_timeout,  # 写入超时
                connect_timeout=10  # 连接超时
            )
            
            # 设置只读模式和低优先级
            if self.read_only_mode:
                try:
                    with self._connection.cursor() as cursor:
                        cursor.execute("SET SESSION TRANSACTION READ ONLY")
                        if self.low_priority:
                            # MySQL 8.0+ 支持查询优先级
                            cursor.execute("SET SESSION query_priority = LOW")
                except Exception as e:
                    logger.warning(f"设置只读模式失败（可能MySQL版本不支持）: {e}")
            
            logger.info(f"已建立数据库连接（只读模式: {self.read_only_mode}, 低优先级: {self.low_priority}）")
        return self._connection
    
    def collect(self) -> Dict[str, Any]:
        """收集MySQL数据库信息（已优化：最小化对数据库的影响）"""
        result = {
            'database_type': 'MySQL',
            'host': self.host,
            'port': self.port,
            'database': self.database or 'all',
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
            cursor = conn.cursor()
            
            # 为每个查询设置超时（防止长时间占用）
            cursor.execute(f"SET SESSION max_execution_time = {self.query_timeout * 1000}")
            
            # 收集慢查询（优化：限制查询时间，避免长时间占用）
            if self.collect_slow_queries:
                try:
                    # 设置查询超时
                    cursor.execute(f"SET SESSION max_execution_time = {self.query_timeout * 1000}")
                    
                    cursor.execute("""
                        SELECT 
                            sql_text,
                            exec_count,
                            avg_timer_wait/1000000000000 as avg_time_sec,
                            max_timer_wait/1000000000000 as max_time_sec,
                            sum_timer_wait/1000000000000 as sum_time_sec
                        FROM performance_schema.events_statements_summary_by_digest
                        WHERE avg_timer_wait > 0
                        ORDER BY sum_timer_wait DESC
                        LIMIT %s
                    """, (self.slow_query_limit,))
                    result['slow_queries'] = cursor.fetchall()
                    logger.info(f"收集到 {len(result['slow_queries'])} 条慢查询")
                except Exception as e:
                    logger.warning(f"收集慢查询失败: {e}")
                    err_msg = f"慢查询收集失败: {str(e)}"
                    # 权限不足时给出可操作建议
                    if getattr(e, "args", None) and len(e.args) >= 1 and e.args[0] == 1142:
                        err_msg += "（当前用户无 performance_schema 查询权限。可授予 SELECT ON performance_schema.* 或关闭「收集慢查询」）"
                    result['errors'].append(err_msg)
            
            # 收集进程列表（轻量级查询，影响很小）
            if self.collect_processlist:
                try:
                    cursor.execute("SHOW PROCESSLIST")
                    result['processlist'] = cursor.fetchall()
                    logger.info(f"收集到 {len(result['processlist'])} 个进程")
                except Exception as e:
                    logger.warning(f"收集进程列表失败: {e}")
                    result['errors'].append(f"进程列表收集失败: {str(e)}")
            
            # 收集状态信息（轻量级查询，影响很小）
            if self.collect_status:
                try:
                    cursor.execute("SHOW GLOBAL STATUS")
                    status_rows = cursor.fetchall()
                    result['status'] = {row['Variable_name']: row['Value'] for row in status_rows}
                    logger.info(f"收集到 {len(result['status'])} 个状态变量")
                except Exception as e:
                    logger.warning(f"收集状态信息失败: {e}")
                    result['errors'].append(f"状态信息收集失败: {str(e)}")
            
            # 收集配置变量（轻量级查询，影响很小）
            if self.collect_variables:
                try:
                    cursor.execute("SHOW VARIABLES")
                    var_rows = cursor.fetchall()
                    result['variables'] = {row['Variable_name']: row['Value'] for row in var_rows}
                    logger.info(f"收集到 {len(result['variables'])} 个配置变量")
                except Exception as e:
                    logger.warning(f"收集配置变量失败: {e}")
                    result['errors'].append(f"配置变量收集失败: {str(e)}")
            
            # 收集索引信息（优化：限制数量，避免查询大量数据）
            if self.collect_indexes:
                try:
                    # 重新设置查询超时（确保每个查询都有超时保护）
                    cursor.execute(f"SET SESSION max_execution_time = {self.query_timeout * 1000}")
                    
                    if self.database:
                        cursor.execute(f"""
                            SELECT 
                                TABLE_SCHEMA,
                                TABLE_NAME,
                                INDEX_NAME,
                                COLUMN_NAME,
                                SEQ_IN_INDEX,
                                NON_UNIQUE,
                                CARDINALITY
                            FROM information_schema.STATISTICS
                            WHERE TABLE_SCHEMA = %s
                            ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
                            LIMIT %s
                        """, (self.database, self.index_limit))
                    else:
                        cursor.execute(f"""
                            SELECT 
                                TABLE_SCHEMA,
                                TABLE_NAME,
                                INDEX_NAME,
                                COLUMN_NAME,
                                SEQ_IN_INDEX,
                                NON_UNIQUE,
                                CARDINALITY
                            FROM information_schema.STATISTICS
                            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                            ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
                            LIMIT %s
                        """, (self.index_limit,))
                    result['indexes'] = cursor.fetchall()
                    logger.info(f"收集到 {len(result['indexes'])} 条索引信息（限制: {self.index_limit}）")
                except Exception as e:
                    logger.warning(f"收集索引信息失败: {e}")
                    result['errors'].append(f"索引信息收集失败: {str(e)}")
            
            # 收集表信息（优化：限制数量，避免查询大量数据）
            if self.collect_tables:
                try:
                    # 设置查询超时
                    cursor.execute(f"SET SESSION max_execution_time = {self.query_timeout * 1000}")
                    
                    if self.database:
                        cursor.execute(f"""
                            SELECT 
                                TABLE_SCHEMA,
                                TABLE_NAME,
                                TABLE_ROWS,
                                DATA_LENGTH,
                                INDEX_LENGTH,
                                DATA_FREE,
                                ENGINE,
                                TABLE_COLLATION
                            FROM information_schema.TABLES
                            WHERE TABLE_SCHEMA = %s
                            LIMIT %s
                        """, (self.database, self.table_limit))
                    else:
                        cursor.execute(f"""
                            SELECT 
                                TABLE_SCHEMA,
                                TABLE_NAME,
                                TABLE_ROWS,
                                DATA_LENGTH,
                                INDEX_LENGTH,
                                DATA_FREE,
                                ENGINE,
                                TABLE_COLLATION
                            FROM information_schema.TABLES
                            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                            LIMIT %s
                        """, (self.table_limit,))
                    result['tables'] = cursor.fetchall()
                    logger.info(f"收集到 {len(result['tables'])} 个表信息（限制: {self.table_limit}）")
                except Exception as e:
                    logger.warning(f"收集表信息失败: {e}")
                    result['errors'].append(f"表信息收集失败: {str(e)}")
            
            cursor.close()
            
        except Exception as e:
            logger.error(f"收集MySQL数据失败: {e}", exc_info=True)
            result['errors'].append(f"数据收集失败: {str(e)}")
        finally:
            if self._connection and self._connection.open:
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
            logger.error(f"MySQL连接验证失败: {e}")
            return False
