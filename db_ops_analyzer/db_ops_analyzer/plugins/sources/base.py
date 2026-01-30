"""数据源插件基类"""

from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any
from db_ops_analyzer.plugins.base import Plugin


class AbstractSource(Plugin):
    """数据源插件基类"""
    
    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """
        收集数据库信息
        
        Returns:
            包含数据库信息的字典，格式：
            {
                'slow_queries': [...],
                'processlist': [...],
                'status': {...},
                'variables': {...},
                'indexes': [...],
                'tables': [...],
                ...
            }
        """
        pass
    
    def validate(self) -> bool:
        """验证配置"""
        return True
