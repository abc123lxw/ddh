"""输出插件基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from db_ops_analyzer.plugins.base import Plugin


class AbstractSink(Plugin):
    """输出插件基类"""
    
    @abstractmethod
    def save(self, result: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        保存分析结果
        
        Args:
            result: 分析结果（通常是Markdown格式）
            metadata: 元数据（任务名、时间戳等）
            
        Returns:
            保存路径（如果适用）
        """
        pass
    
    def validate(self) -> bool:
        """验证配置"""
        return True
