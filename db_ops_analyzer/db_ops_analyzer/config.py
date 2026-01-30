"""配置加载模块"""

import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径，默认为 config.yaml
        """
        if config_path is None:
            config_path = os.getenv("CONFIG_PATH", "config.yaml")
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f) or {}
        
        logger.info(f"配置文件加载成功: {self.config_path}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def get_tasks(self) -> list:
        """获取任务列表"""
        return self._config.get('tasks', [])
    
    def get_task(self, task_name: str) -> Optional[Dict[str, Any]]:
        """获取指定任务配置"""
        tasks = self.get_tasks()
        for task in tasks:
            if task.get('name') == task_name:
                return task
        return None
    
    @property
    def server(self) -> Dict[str, Any]:
        """获取服务器配置"""
        # 优先使用环境变量，然后是配置文件
        default_port = int(os.getenv("SERVER_PORT", "8000"))
        default_host = os.getenv("SERVER_HOST", "0.0.0.0")
        
        server_config = self._config.get('server', {})
        return {
            'host': os.getenv("SERVER_HOST", server_config.get('host', default_host)),
            'port': int(os.getenv("SERVER_PORT", str(server_config.get('port', default_port))))
        }
    
    def get_monitoring_config(self) -> Optional[Dict[str, Any]]:
        """获取监控配置"""
        return self._config.get('monitoring')
