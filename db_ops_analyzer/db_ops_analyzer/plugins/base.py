"""插件基类"""

from abc import ABC


class Plugin(ABC):
    """插件基类"""
    
    def __init__(self, **kwargs):
        """初始化插件"""
        self.config = kwargs
    
    def validate(self) -> bool:
        """验证配置"""
        return True
