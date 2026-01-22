"""数据源插件基类"""

from abc import ABC, abstractmethod
from typing import Iterable
from log_analyzer.plugins.base import Plugin


class AbstractSource(Plugin):
    """数据源插件基类"""
    
    @abstractmethod
    def collect(self) -> Iterable[str]:
        """
        收集数据
        
        Returns:
            数据迭代器
        """
        pass
    
    def validate(self) -> bool:
        """验证配置"""
        return True
