"""Docker容器日志数据源"""

import logging
import os
from typing import Iterable, Optional
from datetime import datetime, timedelta
from log_analyzer.plugins.sources.base import AbstractSource

try:
    import docker
except ImportError:
    docker = None

logger = logging.getLogger(__name__)


class DockerSource(AbstractSource):
    """从Docker容器收集日志"""
    
    def __init__(
        self, 
        container_name: str, 
        hours_ago: Optional[int] = None,
        minutes_ago: Optional[int] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        tail: Optional[int] = None,
        max_lines: Optional[int] = None,
        max_bytes: Optional[int] = None,
        **kwargs
    ):
        """
        初始化Docker数据源
        
        Args:
            container_name: 容器名称
            hours_ago: 获取多少小时前的日志（优先级低于minutes_ago）
            minutes_ago: 获取多少分钟前的日志（如果指定，会覆盖hours_ago）
            since: 指定开始时间（格式：YYYY-MM-DDTHH:MM:SS 或 YYYY-MM-DD HH:MM:SS）
            until: 指定结束时间（格式：YYYY-MM-DDTHH:MM:SS 或 YYYY-MM-DD HH:MM:SS）
            tail: 限制日志尾部行数（默认5000，最大50000）
            max_lines: 额外行数上限（可选）
            max_bytes: 字节上限（可选）
        """
        super().__init__(**kwargs)
        self.container_name = container_name
        self.since = since
        self.until = until
        
        # 优先使用minutes_ago，如果没有则使用hours_ago，默认24小时
        if minutes_ago is not None:
            self.minutes_ago = minutes_ago
            self.hours_ago = None
        elif hours_ago is not None:
            self.hours_ago = hours_ago
            self.minutes_ago = None
        else:
            self.hours_ago = 24
            self.minutes_ago = None

        # 限流参数 - 优化默认值以提升速度
        default_tail = 3000  # 减小默认值，提升收集速度
        max_tail_cap = 50000
        self.tail = min(tail or default_tail, max_tail_cap)
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        
        # 初始化Docker客户端
        if docker is None:
            logger.error("docker包未安装，请运行: pip install docker")
            self.client = None
        else:
            try:
                # 尝试连接到Docker socket
                self.client = docker.from_env()
                # 测试连接
                self.client.ping()
                logger.info("Docker客户端连接成功")
            except Exception as e:
                logger.warning(f"Docker客户端连接失败: {e}，将尝试使用subprocess")
                self.client = None
    
    def collect(self) -> Iterable[str]:
        """收集Docker容器日志"""
        try:
            # 计算时间范围
            if self.since:
                # 使用指定的开始时间
                since_str = self.since.replace(' ', 'T')
                if 'T' not in since_str:
                    since_str = since_str.replace(' ', 'T')
                try:
                    since_time = datetime.strptime(since_str, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    since_time = datetime.now() - timedelta(hours=24)
            elif self.minutes_ago is not None:
                since_time = datetime.now() - timedelta(minutes=self.minutes_ago)
                since_str = since_time.strftime('%Y-%m-%dT%H:%M:%S')
            else:
                since_time = datetime.now() - timedelta(hours=self.hours_ago)
                since_str = since_time.strftime('%Y-%m-%dT%H:%M:%S')
            
            logger.info(f"收集Docker日志: {self.container_name} (since {since_str}, tail={self.tail})")
            
            # 使用Docker SDK
            if self.client is not None:
                try:
                    container = self.client.containers.get(self.container_name)
                    logs = container.logs(
                        since=since_time,
                        timestamps=True,
                        tail=self.tail
                    )
                    logs = logs.decode('utf-8', errors='ignore')
                except docker.errors.NotFound:
                    logger.error(f"容器 {self.container_name} 不存在")
                    return ""
                except Exception as e:
                    logger.error(f"使用Docker SDK收集日志失败: {e}，尝试使用subprocess")
                    self.client = None
            
            # 如果Docker SDK不可用，回退到subprocess
            if self.client is None:
                import subprocess
                cmd = [
                    'docker', 'logs',
                    '--since', since_str,
                    '--timestamps',
                    f'--tail={self.tail}',
                    self.container_name
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if result.returncode != 0:
                    logger.error(f"Docker日志收集失败: {result.stderr}")
                    return ""
                
                logs = result.stdout
            
            if not logs:
                logger.warning(f"容器 {self.container_name} 没有日志")
                return ""

            # 预过滤：只保留可能包含错误的日志行（提升分析速度）
            error_keywords = ['error', 'exception', 'failed', 'fatal', 'critical', 'warning', 'err', 'fail']
            filtered_lines = []
            for line in logs.split('\n'):
                line_lower = line.lower()
                # 保留包含错误关键词的行，或包含堆栈跟踪的行
                if any(keyword in line_lower for keyword in error_keywords) or \
                   'traceback' in line_lower or 'stack' in line_lower or \
                   'exception' in line_lower or 'error' in line_lower:
                    filtered_lines.append(line)
            
            # 如果过滤后还有日志，使用过滤后的；否则使用原始日志（避免全部过滤掉）
            if filtered_lines:
                logs = '\n'.join(filtered_lines)
                logger.info(f"预过滤后保留 {len(filtered_lines)} 行可能包含错误的日志")
            else:
                logger.info("预过滤未发现错误关键词，保留所有日志进行分析")

            # 额外的行数/字节限制
            if self.max_lines is not None:
                lines = logs.split('\n')
                logs = '\n'.join(lines[-self.max_lines:])
            if self.max_bytes is not None and len(logs.encode('utf-8')) > self.max_bytes:
                logs = logs.encode('utf-8')[-self.max_bytes:].decode('utf-8', errors='ignore')
            
            # 如果指定了结束时间，过滤日志
            if self.until:
                until_str = self.until.replace(' ', 'T')
                if 'T' not in until_str:
                    until_str = until_str.replace(' ', 'T')
                try:
                    until_time = datetime.strptime(until_str, '%Y-%m-%dT%H:%M:%S')
                    filtered_lines = []
                    for line in logs.split('\n'):
                        if line.strip():
                            # 尝试解析时间戳（Docker日志格式：2024-01-01T12:00:00.123456789Z ...）
                            try:
                                # 提取时间戳部分
                                timestamp_part = line.split(' ')[0] if ' ' in line else line
                                # 移除微秒和时区信息
                                timestamp_clean = timestamp_part.split('.')[0].rstrip('Z')
                                log_time = datetime.strptime(timestamp_clean, '%Y-%m-%dT%H:%M:%S')
                                if log_time <= until_time:
                                    filtered_lines.append(line)
                            except (ValueError, IndexError):
                                # 如果无法解析时间戳，保留该行
                                filtered_lines.append(line)
                    logs = '\n'.join(filtered_lines)
                    logger.info(f"过滤后日志: {len(logs)} 字符")
                except ValueError as e:
                    logger.warning(f"无法解析结束时间 {until_str}: {e}，跳过过滤")
            
            logger.info(f"成功收集 {len(logs)} 字符的日志")
            return logs
            
        except Exception as e:
            logger.error(f"收集Docker日志异常: {e}", exc_info=True)
            return ""
