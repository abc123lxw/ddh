"""文件日志数据源"""

import os
import logging
from typing import Iterable
from pathlib import Path
from log_analyzer.plugins.sources.base import AbstractSource

logger = logging.getLogger(__name__)


class FileSource(AbstractSource):
    """从文件读取日志"""
    
    def __init__(self, file_path: str, encoding: str = 'utf-8', **kwargs):
        """
        初始化文件数据源
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
        """
        super().__init__(**kwargs)
        self.file_path = Path(file_path)
        self.encoding = encoding
    
    def collect(self) -> Iterable[str]:
        """收集文件日志"""
        if not self.file_path.exists():
            logger.warning(f"文件不存在: {self.file_path}")
            return
        
        try:
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                for line in f:
                    yield line
            logger.info(f"成功读取文件: {self.file_path}")
        except Exception as e:
            logger.error(f"读取文件失败: {e}", exc_info=True)
