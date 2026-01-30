"""Redis数据源插件"""

import logging
from typing import Dict, Any, Optional, List
import redis
from db_ops_analyzer.plugins.sources.base import AbstractSource

logger = logging.getLogger(__name__)


class RedisSource(AbstractSource):
    """Redis数据源插件"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 6379,
                 password: Optional[str] = None,
                 database: int = 0,
                 collect_info: bool = True,
                 collect_slowlog: bool = True,
                 collect_clients: bool = True,
                 collect_memory: bool = True,
                 collect_keyspace: bool = True,
                 collect_config: bool = True,
                 slowlog_limit: int = 100,
                 # 性能优化参数
                 socket_timeout: int = 30,  # 连接超时时间（秒）
                 socket_connect_timeout: int = 10,  # 连接建立超时
                 **kwargs):
        """
        初始化Redis数据源
        
        Args:
            host: Redis主机地址
            port: Redis端口
            password: 密码（可选）
            database: 数据库编号（0-15）
            collect_info: 是否收集INFO信息
            collect_slowlog: 是否收集慢查询日志
            collect_clients: 是否收集客户端连接信息
            collect_memory: 是否收集内存信息
            collect_keyspace: 是否收集键空间信息
            collect_config: 是否收集配置信息
            slowlog_limit: 慢查询日志记录数限制
            socket_timeout: Socket超时时间（秒）
            socket_connect_timeout: 连接建立超时（秒）
        """
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.password = password
        self.database = database
        self.collect_info = collect_info
        self.collect_slowlog = collect_slowlog
        self.collect_clients = collect_clients
        self.collect_memory = collect_memory
        self.collect_keyspace = collect_keyspace
        self.collect_config = collect_config
        self.slowlog_limit = slowlog_limit
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self._client = None
    
    def _get_client(self):
        """获取Redis客户端连接"""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.database,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_connect_timeout,
                decode_responses=True  # 自动解码响应
            )
            # 测试连接
            self._client.ping()
            logger.info(f"已建立Redis连接（数据库: {self.database}）")
        return self._client
    
    def collect(self) -> Dict[str, Any]:
        """收集Redis数据库信息"""
        result = {
            'database_type': 'Redis',
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'info': {},
            'slowlog': [],
            'clients': {},
            'memory': {},
            'keyspace': {},
            'config': {},
            'errors': []
        }
        
        try:
            client = self._get_client()
            
            # 收集INFO信息
            if self.collect_info:
                try:
                    info_all = client.info()
                    result['info'] = info_all
                    logger.info("收集到Redis INFO信息")
                except Exception as e:
                    logger.warning(f"收集INFO信息失败: {e}")
                    result['errors'].append(f"INFO信息收集失败: {str(e)}")
            
            # 收集慢查询日志
            if self.collect_slowlog:
                try:
                    slowlog = client.slowlog_get(self.slowlog_limit)
                    result['slowlog'] = []
                    for log in slowlog:
                        try:
                            # 处理 command 字段（可能是字节串或字符串）
                            command = log.get('command', [])
                            if isinstance(command, list):
                                # 将列表中的元素转换为字符串
                                command_str = ' '.join(str(c) if isinstance(c, bytes) else c for c in command)
                            else:
                                command_str = str(command) if isinstance(command, bytes) else command
                            
                            result['slowlog'].append({
                                'id': log.get('id', 0),
                                'timestamp': log.get('start_time', 0),
                                'duration': log.get('duration', 0) / 1000.0,  # 转换为秒
                                'command': command_str,
                                'client': log.get('client_addr', ''),
                                'client_name': log.get('client_name', '')
                            })
                        except Exception as e:
                            logger.warning(f"处理慢查询日志条目失败: {e}")
                            continue
                    logger.info(f"收集到 {len(result['slowlog'])} 条慢查询日志")
                except Exception as e:
                    logger.warning(f"收集慢查询日志失败: {e}")
                    result['errors'].append(f"慢查询日志收集失败: {str(e)}")
            
            # 收集客户端连接信息
            if self.collect_clients:
                try:
                    client_list = client.client_list()
                    result['clients'] = {
                        'total': len(client_list),
                        'clients': [
                            {
                                'id': cli_info.get('id', ''),
                                'addr': cli_info.get('addr', ''),
                                'name': cli_info.get('name', ''),
                                'age': cli_info.get('age', ''),
                                'idle': cli_info.get('idle', ''),
                                'flags': cli_info.get('flags', ''),
                                'db': cli_info.get('db', ''),
                                'cmd': cli_info.get('cmd', '')
                            }
                            for cli_info in client_list
                        ]
                    }
                    logger.info(f"收集到 {result['clients']['total']} 个客户端连接")
                except Exception as e:
                    logger.warning(f"收集客户端信息失败: {e}")
                    result['errors'].append(f"客户端信息收集失败: {str(e)}")
            
            # 收集内存信息
            if self.collect_memory:
                try:
                    memory_info = client.info('memory')
                    result['memory'] = {
                        'used_memory': memory_info.get('used_memory', 0),
                        'used_memory_human': memory_info.get('used_memory_human', ''),
                        'used_memory_rss': memory_info.get('used_memory_rss', 0),
                        'used_memory_peak': memory_info.get('used_memory_peak', 0),
                        'used_memory_peak_human': memory_info.get('used_memory_peak_human', ''),
                        'mem_fragmentation_ratio': memory_info.get('mem_fragmentation_ratio', 0),
                        'maxmemory': memory_info.get('maxmemory', 0),
                        'maxmemory_human': memory_info.get('maxmemory_human', ''),
                        'maxmemory_policy': memory_info.get('maxmemory_policy', '')
                    }
                    logger.info("收集到内存信息")
                except Exception as e:
                    logger.warning(f"收集内存信息失败: {e}")
                    result['errors'].append(f"内存信息收集失败: {str(e)}")
            
            # 收集键空间信息
            if self.collect_keyspace:
                try:
                    keyspace_info = client.info('keyspace')
                    result['keyspace'] = keyspace_info
                    
                    # 统计每个数据库的键数量
                    db_stats = {}
                    for key, value in keyspace_info.items():
                        if key.startswith('db') and isinstance(value, str):
                            db_num = key[2:]
                            # 解析 keys=123,expires=45 格式
                            stats = {}
                            try:
                                for stat in value.split(','):
                                    if '=' in stat:
                                        k, v = stat.split('=', 1)
                                        try:
                                            stats[k] = int(v)
                                        except ValueError:
                                            stats[k] = v  # 如果不是数字，保留原值
                                db_stats[db_num] = stats
                            except Exception as e:
                                logger.warning(f"解析键空间信息 {key} 失败: {e}")
                                continue
                    result['keyspace']['db_stats'] = db_stats
                    
                    logger.info("收集到键空间信息")
                except Exception as e:
                    logger.warning(f"收集键空间信息失败: {e}")
                    result['errors'].append(f"键空间信息收集失败: {str(e)}")
            
            # 收集配置信息
            if self.collect_config:
                try:
                    redis_config = client.config_get()
                    result['config'] = redis_config
                    logger.info(f"收集到 {len(redis_config)} 个配置项")
                except Exception as e:
                    logger.warning(f"收集配置信息失败: {e}")
                    result['errors'].append(f"配置信息收集失败: {str(e)}")
            
        except Exception as e:
            logger.error(f"收集Redis数据失败: {e}", exc_info=True)
            result['errors'].append(f"数据收集失败: {str(e)}")
        finally:
            if self._client:
                try:
                    self._client.close()
                except:
                    pass
                self._client = None
        
        return result
    
    def validate(self) -> bool:
        """验证配置"""
        try:
            client = self._get_client()
            client.ping()
            client.close()
            return True
        except Exception as e:
            logger.error(f"Redis连接验证失败: {e}")
            return False
