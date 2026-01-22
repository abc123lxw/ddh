"""数据源插件"""

from log_analyzer.plugins.sources.base import AbstractSource
from log_analyzer.plugins.sources.docker import DockerSource
from log_analyzer.plugins.sources.file import FileSource
from log_analyzer.plugins.sources.multi import MultiSource

__all__ = ['AbstractSource', 'DockerSource', 'FileSource', 'MultiSource']
