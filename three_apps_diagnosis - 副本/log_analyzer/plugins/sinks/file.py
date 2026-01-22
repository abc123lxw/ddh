"""文件存储插件"""

import os
import logging
from typing import Any, Optional
from pathlib import Path
from datetime import datetime
from log_analyzer.plugins.sinks.base import AbstractSink

logger = logging.getLogger(__name__)


class FileSink(AbstractSink):
    """保存到文件"""
    
    def __init__(self, output_path: str = "reports/report_{timestamp}.md", **kwargs):
        """
        初始化文件存储
        
        Args:
            output_path: 输出文件路径，支持 {timestamp} 和 {container_name} 占位符
        """
        super().__init__(**kwargs)
        self.output_path_template = output_path
    
    def save(self, data: Any, metadata: dict = None) -> Any:
        """保存到文件"""
        try:
            # 替换占位符
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            container_name = (metadata or {}).get('container_name', 'all')
            
            # 处理 YAML 中可能的双大括号转义 {{timestamp}} -> {timestamp}
            template = self.output_path_template.replace('{{timestamp}}', '{timestamp}')
            template = template.replace('{{{{timestamp}}}}', '{timestamp}')  # 处理可能的四重大括号
            template = template.replace('{{container_name}}', '{container_name}')
            template = template.replace('{{{{container_name}}}}', '{container_name}')
            
            # 替换占位符
            output_path = template.format(timestamp=timestamp, container_name=container_name)
            
            # 创建目录
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                f.write(str(data))
            
            logger.info(f"保存到文件: {output_path}")
            return str(path.absolute())
            
        except Exception as e:
            logger.error(f"保存到文件失败: {e}", exc_info=True)
            return None
