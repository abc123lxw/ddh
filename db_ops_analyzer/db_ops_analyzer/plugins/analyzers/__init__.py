"""分析器插件"""

from db_ops_analyzer.plugins.analyzers.base import AbstractAnalyzer
from db_ops_analyzer.plugins.analyzers.langgraph import LangGraphAnalyzer

__all__ = ['AbstractAnalyzer', 'LangGraphAnalyzer']
