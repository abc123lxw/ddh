"""输出插件"""

from log_analyzer.plugins.sinks.base import AbstractSink
from log_analyzer.plugins.sinks.database import DatabaseSink
from log_analyzer.plugins.sinks.file import FileSink
from log_analyzer.plugins.sinks.minio import MinIOSink

__all__ = ['AbstractSink', 'DatabaseSink', 'FileSink', 'MinIOSink']
