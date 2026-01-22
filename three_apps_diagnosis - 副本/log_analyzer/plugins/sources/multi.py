"""
MultiSource Plugin - 聚合多个数据源的 Source 插件
支持同时从多个 Source（Docker、File、SQL等）收集数据，按时间线合并
"""

import logging
from typing import Iterable, List, Dict, Any, Optional
from datetime import datetime
from log_analyzer.plugins.sources.base import AbstractSource

# 动态导入其他 Source 插件
try:
    from log_analyzer.plugins.sources.docker import DockerSource
except ImportError:
    DockerSource = None

try:
    from log_analyzer.plugins.sources.file import FileSource
except ImportError:
    FileSource = None

try:
    from log_analyzer.plugins.sources.sql import SQLSource
except ImportError:
    SQLSource = None

try:
    from log_analyzer.plugins.sources.litellm import LiteLLMSource
except ImportError:
    LiteLLMSource = None


class MultiSource(AbstractSource):
    """
    聚合多个 Source 插件，统一收集数据并按时间线合并
    
    支持的数据源类型：
    - docker: Docker 容器日志
    - file: 文件日志
    - sql: SQL 查询结果
    - litellm: LiteLLM 数据库日志
    """

    def __init__(self, sources: List[Dict[str, Any]], call_chain: Optional[List[Dict[str, str]]] = None, **kwargs):
        """
        初始化 MultiSource
        
        Args:
            sources: 数据源配置列表，每个配置包含：
                - type: 数据源类型 (docker/file/sql/litellm)
                - label: 数据源标签（用于标识来源，如应用名称）
                - 其他参数传递给对应的 Source 插件
            call_chain: 可选，定义应用间的调用关系
                - from: 源应用名称
                - to: 目标应用名称
                - protocol: 调用协议（如 HTTP SSE、MCP）
        """
        super().__init__(**kwargs)
        
        self.sources_config = sources
        self.call_chain = call_chain or []
        self.source_instances = []
        
        # 初始化各个 Source 实例
        for source_cfg in sources:
            source_type = source_cfg.get("type")
            source_label = source_cfg.get("label", "unknown")
            source_params = {k: v for k, v in source_cfg.items() if k not in ["type", "label"]}
            
            try:
                source_instance = self._create_source(source_type, source_params)
                if source_instance:
                    source_instance.label = source_label  # 添加标签属性
                    self.source_instances.append(source_instance)
                    logging.info(f"MultiSource: Added source '{source_type}' with label '{source_label}'")
                else:
                    logging.warning(f"MultiSource: Failed to create source '{source_type}', skipping")
            except Exception as e:
                logging.error(f"MultiSource: Error creating source '{source_type}': {e}", exc_info=True)
        
        if not self.source_instances:
            raise ValueError("MultiSource: No valid sources created")
        
        logging.info(f"MultiSource initialized with {len(self.source_instances)} source(s)")

    def _create_source(self, source_type: str, params: Dict[str, Any]) -> Optional[AbstractSource]:
        """根据类型创建对应的 Source 实例"""
        source_map = {
            "docker": DockerSource,
            "file": FileSource,
            "sql": SQLSource,
            "litellm": LiteLLMSource,
        }
        
        source_class = source_map.get(source_type)
        if not source_class:
            logging.error(f"Unknown source type: {source_type}")
            return None
        
        try:
            return source_class(**params)
        except Exception as e:
            logging.error(f"Failed to create {source_type} source: {e}")
            return None

    def collect(self) -> Iterable[str]:
        """
        收集所有 Source 的数据，按时间线合并
        
        返回格式：
        [时间戳] [应用标签] 日志内容
        """
        all_logs = []
        
        # 从各个 Source 收集数据
        for source_instance in self.source_instances:
            label = getattr(source_instance, "label", "unknown")
            try:
                result = source_instance.collect()
                
                # 处理不同的返回类型
                if isinstance(result, str):
                    # DockerSource 返回字符串
                    if result:
                        all_logs.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S"), label, result))
                        logging.info(f"MultiSource: Collected log from '{label}' (string)")
                elif hasattr(result, '__iter__'):
                    # 其他 Source 返回 Iterable
                    for log_chunk in result:
                        if log_chunk:
                            all_logs.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S"), label, log_chunk))
                            logging.info(f"MultiSource: Collected log from '{label}' (iterable)")
                else:
                    logging.warning(f"MultiSource: Unknown return type from '{label}' source")
                    
            except Exception as e:
                logging.error(f"MultiSource: Error collecting from '{label}': {e}", exc_info=True)
        
        if not all_logs:
            logging.warning("MultiSource: No logs collected from any source")
            return  # 返回空迭代器（生成器函数直接return会返回空迭代器）
        
        # 按时间戳排序
        all_logs.sort(key=lambda x: x[0])
        
        # 添加调用关系信息（如果有）
        if self.call_chain:
            call_chain_info = "\n".join([
                f"# 调用关系: {chain['from']} -> {chain['to']} ({chain.get('protocol', 'unknown')})"
                for chain in self.call_chain
            ])
            yield call_chain_info + "\n\n"
        
        # 格式化输出
        for timestamp, label, log_content in all_logs:
            # 如果日志内容是多行，每行都添加标签
            lines = log_content.split('\n')
            for line in lines:
                if line.strip():  # 忽略空行
                    yield f"[{timestamp}] [{label}] {line}\n"
