"""数据库存储插件"""

import logging
from typing import Any, Optional
from datetime import datetime
from log_analyzer.plugins.sinks.base import AbstractSink

logger = logging.getLogger(__name__)


class DatabaseSink(AbstractSink):
    """保存到数据库"""
    
    def __init__(self, connection_string: Optional[str] = None, **kwargs):
        """
        初始化数据库存储
        
        Args:
            connection_string: 数据库连接字符串
        """
        super().__init__(**kwargs)
        self.connection_string = connection_string
        self._db = None
    
    def _get_db(self):
        """获取数据库连接（懒加载）"""
        if self._db is None:
            # 这里可以集成SQLite、PostgreSQL等
            # 暂时使用简单的内存存储
            if not hasattr(DatabaseSink, '_storage'):
                DatabaseSink._storage = []
            self._db = DatabaseSink._storage
        return self._db
    
    def save(self, data: Any, metadata: dict = None) -> Any:
        """保存到数据库"""
        try:
            db = self._get_db()
            record = {
                'id': len(db) + 1,
                'content': str(data),
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat()
            }
            db.append(record)
            logger.info(f"保存到数据库: ID={record['id']}")
            return record['id']
        except Exception as e:
            logger.error(f"保存到数据库失败: {e}", exc_info=True)
            return None
