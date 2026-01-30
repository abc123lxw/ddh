"""分析器插件基类"""

from abc import ABC, abstractmethod
from typing import Any
from db_ops_analyzer.plugins.base import Plugin


class AbstractAnalyzer(Plugin):
    """分析器插件基类"""
    
    @abstractmethod
    def analyze(self, data: Any) -> str:
        """
        分析数据
        
        Args:
            data: 待分析的数据（通常是Source收集的字典）
            
        Returns:
            分析结果（Markdown格式报告）
        """
        pass
    
    def validate(self) -> bool:
        """验证配置"""
        return True
