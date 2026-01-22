"""输出插件基类"""

from abc import ABC, abstractmethod
from typing import Any
from log_analyzer.plugins.base import Plugin


class AbstractSink(Plugin):
    """输出插件基类"""
    
    @abstractmethod
    def save(self, data: Any, metadata: dict = None) -> Any:
        """
        保存数据
        
        Args:
            data: 要保存的数据
            metadata: 元数据（如报告ID、时间戳等）
            
        Returns:
            保存结果（如文件路径、数据库ID等）
        """
        pass
    
    def validate(self) -> bool:
        """验证配置"""
        return True
