"""文件输出插件"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from db_ops_analyzer.plugins.sinks.base import AbstractSink

logger = logging.getLogger(__name__)


class FileSink(AbstractSink):
    """保存到文件"""
    
    def __init__(self, output_path: str = "reports/db_analysis_{{timestamp}}.md", **kwargs):
        """
        初始化文件输出插件
        
        Args:
            output_path: 输出文件路径，支持 {timestamp} 占位符
        """
        super().__init__(**kwargs)
        self.output_path_template = output_path
    
    def save(self, result: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """保存到文件"""
        # 替换占位符
        output_path = self.output_path_template
        if '{timestamp}' in output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = output_path.replace('{timestamp}', timestamp)
        
        # 如果metadata中有timestamp，也替换
        if metadata and 'timestamp' in metadata:
            output_path = output_path.replace('{timestamp}', metadata['timestamp'])
        
        # 创建目录
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            
            logger.info(f"分析结果已保存到: {output_path}")
            return str(output_file.absolute())
        except Exception as e:
            logger.error(f"保存文件失败: {e}", exc_info=True)
            return None
