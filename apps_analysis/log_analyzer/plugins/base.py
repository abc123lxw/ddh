"""插件基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Plugin(ABC):
    """插件基类"""
    
    def __init__(self, **kwargs):
        """初始化插件"""
        self.params = kwargs
    
    @abstractmethod
    def validate(self) -> bool:
        """验证插件配置"""
        pass
