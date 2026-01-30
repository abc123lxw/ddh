"""输出插件"""

from db_ops_analyzer.plugins.sinks.base import AbstractSink
from db_ops_analyzer.plugins.sinks.file import FileSink

__all__ = ['AbstractSink', 'FileSink']
