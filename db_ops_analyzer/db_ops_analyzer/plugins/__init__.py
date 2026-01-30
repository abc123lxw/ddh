"""插件系统"""

from db_ops_analyzer.plugins.base import Plugin
from db_ops_analyzer.plugins.sources.base import AbstractSource
from db_ops_analyzer.plugins.analyzers.base import AbstractAnalyzer
from db_ops_analyzer.plugins.sinks.base import AbstractSink

__all__ = ['Plugin', 'AbstractSource', 'AbstractAnalyzer', 'AbstractSink']
