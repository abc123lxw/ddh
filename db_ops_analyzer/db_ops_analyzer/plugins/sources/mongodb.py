"""MongoDB数据源插件"""

import logging
from typing import Dict, Any, Optional, List
from pymongo import MongoClient
from pymongo.read_preferences import ReadPreference
from pymongo.errors import ConnectionFailure, OperationFailure
from db_ops_analyzer.plugins.sources.base import AbstractSource

logger = logging.getLogger(__name__)


class MongoDBSource(AbstractSource):
    """MongoDB数据源插件"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 27017,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None,
                 auth_source: Optional[str] = None,
                 collect_server_status: bool = True,
                 collect_database_stats: bool = True,
                 collect_collection_stats: bool = True,
                 collect_indexes: bool = True,
                 collect_operations: bool = True,
                 collect_connections: bool = True,
                 collection_limit: int = 100,  # 集合信息收集限制
                 index_limit: int = 500,  # 索引信息收集限制
                 # 性能优化参数
                 socket_timeout_ms: int = 30000,  # Socket超时（毫秒）
                 connect_timeout_ms: int = 10000,  # 连接超时（毫秒）
                 read_preference: str = "secondaryPreferred",  # 优先从节点读取
                 **kwargs):
        """
        初始化MongoDB数据源
        
        Args:
            host: MongoDB主机地址
            port: MongoDB端口
            user: 用户名（可选）
            password: 密码（可选）
            database: 数据库名（可选，不指定则分析所有数据库）
            auth_source: 认证数据库（可选）
            collect_server_status: 是否收集服务器状态
            collect_database_stats: 是否收集数据库统计信息
            collect_collection_stats: 是否收集集合统计信息
            collect_indexes: 是否收集索引信息
            collect_operations: 是否收集操作统计
            collect_connections: 是否收集连接信息
            collection_limit: 集合信息收集限制
            index_limit: 索引信息收集限制
            socket_timeout_ms: Socket超时（毫秒）
            connect_timeout_ms: 连接超时（毫秒）
            read_preference: 读取偏好（secondaryPreferred表示优先从节点）
        """
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.auth_source = auth_source or "admin"
        self.collect_server_status = collect_server_status
        self.collect_database_stats = collect_database_stats
        self.collect_collection_stats = collect_collection_stats
        self.collect_indexes = collect_indexes
        self.collect_operations = collect_operations
        self.collect_connections = collect_connections
        self.collection_limit = collection_limit
        self.index_limit = index_limit
        self.socket_timeout_ms = socket_timeout_ms
        self.connect_timeout_ms = connect_timeout_ms
        self.read_preference = read_preference
        self._client = None
    
    def _get_client(self):
        """获取MongoDB客户端连接"""
        if self._client is None:
            # 转义用户名和密码中的特殊字符
            from urllib.parse import quote_plus
            connection_string = f"mongodb://{self.host}:{self.port}/"
            if self.user and self.password:
                # 对用户名和密码进行 URL 编码，防止特殊字符导致连接失败
                encoded_user = quote_plus(self.user)
                encoded_password = quote_plus(self.password)
                connection_string = f"mongodb://{encoded_user}:{encoded_password}@{self.host}:{self.port}/"
                if self.auth_source:
                    connection_string += f"?authSource={self.auth_source}"
            
            # 转换读取偏好字符串为 ReadPreference 对象
            read_pref_map = {
                'primary': ReadPreference.PRIMARY,
                'primaryPreferred': ReadPreference.PRIMARY_PREFERRED,
                'secondary': ReadPreference.SECONDARY,
                'secondaryPreferred': ReadPreference.SECONDARY_PREFERRED,
                'nearest': ReadPreference.NEAREST
            }
            read_pref = read_pref_map.get(self.read_preference.lower(), ReadPreference.SECONDARY_PREFERRED)
            
            self._client = MongoClient(
                connection_string,
                socketTimeoutMS=self.socket_timeout_ms,
                connectTimeoutMS=self.connect_timeout_ms,
                read_preference=read_pref,
                serverSelectionTimeoutMS=self.connect_timeout_ms
            )
            # 测试连接
            self._client.admin.command('ping')
            logger.info(f"已建立MongoDB连接（主机: {self.host}:{self.port}）")
        return self._client
    
    def collect(self) -> Dict[str, Any]:
        """收集MongoDB数据库信息"""
        result = {
            'database_type': 'MongoDB',
            'host': self.host,
            'port': self.port,
            'database': self.database or 'all',
            'server_status': {},
            'database_stats': {},
            'collections': [],
            'indexes': [],
            'operations': {},
            'connections': {},
            'errors': []
        }
        
        try:
            client = self._get_client()
            
            # 收集服务器状态（如果多个地方需要，只获取一次）
            server_status = None
            if self.collect_server_status or self.collect_operations or self.collect_connections:
                try:
                    server_status = client.admin.command('serverStatus')
                    if self.collect_server_status:
                        result['server_status'] = {
                            'host': server_status.get('host', ''),
                            'version': server_status.get('version', ''),
                            'uptime': server_status.get('uptime', 0),
                            'connections': server_status.get('connections', {}),
                            'network': server_status.get('network', {}),
                            'opcounters': server_status.get('opcounters', {}),
                            'opcountersRepl': server_status.get('opcountersRepl', {}),
                            'mem': server_status.get('mem', {}),
                            'wiredTiger': server_status.get('wiredTiger', {}),
                            'metrics': server_status.get('metrics', {})
                        }
                        logger.info("收集到服务器状态信息")
                except Exception as e:
                    logger.warning(f"收集服务器状态失败: {e}")
                    if self.collect_server_status:
                        result['errors'].append(f"服务器状态收集失败: {str(e)}")
            
            # 收集数据库列表
            database_list = []
            if self.database:
                database_list = [self.database]
            else:
                database_list = client.list_database_names()
                # 排除系统数据库
                database_list = [db for db in database_list if db not in ['admin', 'local', 'config']]
            
            # 收集数据库统计信息
            if self.collect_database_stats:
                try:
                    db_stats = {}
                    for db_name in database_list[:10]:  # 限制最多10个数据库
                        db = client[db_name]
                        stats = db.command('dbStats')
                        db_stats[db_name] = {
                            'collections': stats.get('collections', 0),
                            'objects': stats.get('objects', 0),
                            'dataSize': stats.get('dataSize', 0),
                            'storageSize': stats.get('storageSize', 0),
                            'indexes': stats.get('indexes', 0),
                            'indexSize': stats.get('indexSize', 0)
                        }
                    result['database_stats'] = db_stats
                    logger.info(f"收集到 {len(db_stats)} 个数据库的统计信息")
                except Exception as e:
                    logger.warning(f"收集数据库统计信息失败: {e}")
                    result['errors'].append(f"数据库统计信息收集失败: {str(e)}")
            
            # 收集集合和索引信息
            collections_info = []
            indexes_info = []
            
            for db_name in database_list[:5]:  # 限制最多5个数据库
                db = client[db_name]
                
                # 收集集合信息
                if self.collect_collection_stats:
                    try:
                        collections = db.list_collection_names()
                        for coll_name in collections[:self.collection_limit]:
                            try:
                                coll = db[coll_name]
                                stats = db.command('collStats', coll_name)
                                collections_info.append({
                                    'database': db_name,
                                    'collection': coll_name,
                                    'count': stats.get('count', 0),
                                    'size': stats.get('size', 0),
                                    'storageSize': stats.get('storageSize', 0),
                                    'indexSize': stats.get('totalIndexSize', 0),
                                    'indexes': stats.get('nindexes', 0)
                                })
                            except Exception as e:
                                logger.warning(f"收集集合 {db_name}.{coll_name} 统计失败: {e}")
                    except Exception as e:
                        logger.warning(f"收集数据库 {db_name} 集合信息失败: {e}")
                
                # 收集索引信息
                if self.collect_indexes:
                    try:
                        collections = db.list_collection_names()
                        for coll_name in collections[:10]:  # 每个数据库最多10个集合
                            try:
                                coll = db[coll_name]
                                indexes = list(coll.list_indexes())  # 转换为列表
                                for idx in indexes:
                                    if len(indexes_info) >= self.index_limit:
                                        break
                                    indexes_info.append({
                                        'database': db_name,
                                        'collection': coll_name,
                                        'name': idx.get('name', ''),
                                        'keys': idx.get('key', {}),
                                        'unique': idx.get('unique', False),
                                        'sparse': idx.get('sparse', False)
                                    })
                            except Exception as e:
                                logger.warning(f"收集集合 {db_name}.{coll_name} 索引失败: {e}")
                    except Exception as e:
                        logger.warning(f"收集数据库 {db_name} 索引信息失败: {e}")
            
            result['collections'] = collections_info
            result['indexes'] = indexes_info
            logger.info(f"收集到 {len(collections_info)} 个集合信息和 {len(indexes_info)} 个索引信息")
            
            # 收集操作统计（复用已获取的 server_status）
            if self.collect_operations:
                try:
                    if server_status:
                        result['operations'] = {
                            'opcounters': server_status.get('opcounters', {}),
                            'opcountersRepl': server_status.get('opcountersRepl', {})
                        }
                        logger.info("收集到操作统计信息")
                    else:
                        logger.warning("无法收集操作统计：服务器状态未获取")
                        result['errors'].append("操作统计收集失败: 服务器状态未获取")
                except Exception as e:
                    logger.warning(f"收集操作统计失败: {e}")
                    result['errors'].append(f"操作统计收集失败: {str(e)}")
            
            # 收集连接信息（复用已获取的 server_status）
            if self.collect_connections:
                try:
                    if server_status:
                        result['connections'] = server_status.get('connections', {})
                        logger.info("收集到连接信息")
                    else:
                        logger.warning("无法收集连接信息：服务器状态未获取")
                        result['errors'].append("连接信息收集失败: 服务器状态未获取")
                except Exception as e:
                    logger.warning(f"收集连接信息失败: {e}")
                    result['errors'].append(f"连接信息收集失败: {str(e)}")
            
        except Exception as e:
            logger.error(f"收集MongoDB数据失败: {e}", exc_info=True)
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
            client.admin.command('ping')
            client.close()
            return True
        except Exception as e:
            logger.error(f"MongoDB连接验证失败: {e}")
            return False
