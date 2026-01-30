"""任务执行引擎"""

import logging
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from db_ops_analyzer.config import Config
from db_ops_analyzer.plugins.sources import AbstractSource
from db_ops_analyzer.plugins.analyzers import AbstractAnalyzer
from db_ops_analyzer.plugins.sinks import AbstractSink

logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, config: Config):
        """初始化任务执行器"""
        self.config = config
        self.runs: Dict[int, Dict[str, Any]] = {}
        self.reports: Dict[str, Dict[str, Any]] = {}
        self._run_id_counter = 0
        self._lock = threading.Lock()
    
    def create_source(self, source_config: Dict[str, Any]) -> AbstractSource:
        """创建Source插件实例"""
        source_name = source_config.get('name')
        source_params = source_config.get('params', {})
        
        try:
            if source_name == 'mysql':
                from db_ops_analyzer.plugins.sources.mysql import MySQLSource
                return MySQLSource(**source_params)
            elif source_name == 'postgresql':
                from db_ops_analyzer.plugins.sources.postgresql import PostgreSQLSource
                return PostgreSQLSource(**source_params)
            elif source_name == 'redis':
                from db_ops_analyzer.plugins.sources.redis import RedisSource
                return RedisSource(**source_params)
            elif source_name == 'mongodb':
                from db_ops_analyzer.plugins.sources.mongodb import MongoDBSource
                return MongoDBSource(**source_params)
            else:
                raise ValueError(f"未知的Source插件: {source_name}")
        except Exception as e:
            logger.error(f"创建Source插件失败: {e}", exc_info=True)
            raise
    
    def create_analyzer(self, analyzer_config: Dict[str, Any]) -> AbstractAnalyzer:
        """创建Analyzer插件实例"""
        analyzer_name = analyzer_config.get('name')
        analyzer_params = analyzer_config.get('params', {})
        
        try:
            if analyzer_name == 'langgraph':
                from db_ops_analyzer.plugins.analyzers.langgraph import LangGraphAnalyzer
                return LangGraphAnalyzer(**analyzer_params)
            else:
                raise ValueError(f"未知的Analyzer插件: {analyzer_name}")
        except Exception as e:
            logger.error(f"创建Analyzer插件失败: {e}", exc_info=True)
            raise
    
    def create_sinks(self, sinks_config: list) -> list:
        """创建Sink插件实例列表"""
        sinks = []
        for sink_config in sinks_config:
            sink_name = sink_config.get('name')
            sink_params = sink_config.get('params', {})
            
            try:
                if sink_name == 'file':
                    from db_ops_analyzer.plugins.sinks.file import FileSink
                    sinks.append(FileSink(**sink_params))
                else:
                    logger.warning(f"未知的Sink插件: {sink_name}，跳过")
            except Exception as e:
                logger.error(f"创建Sink插件失败: {e}", exc_info=True)
        
        return sinks
    
    def _create_run(self, task_name: str) -> int:
        """创建run记录"""
        with self._lock:
            run_id = self._run_id_counter + 1
            self._run_id_counter = run_id
        
        run_info = {
            'id': run_id,
            'task_name': task_name,
            'status': 'running',
            'stage': 'queued',
            'progress': {
                'percentage': 0,
                'stage': 'queued'
            },
            'started_at': datetime.now().isoformat(),
            'finished_at': None,
            'error': None
        }
        self.runs[run_id] = run_info
        return run_id
    
    def _run_task(self, run_id: int, task_name: str, task_config: Dict[str, Any]) -> None:
        """执行任务"""
        run_info = self.runs[run_id]
        try:
            logger.info(f"开始执行任务: {task_name} (Run ID: {run_id})")
            
            # 更新状态：收集数据
            run_info['stage'] = 'collecting'
            run_info['progress'] = {'percentage': 10, 'stage': 'collecting'}
            
            # 创建插件实例
            source = self.create_source(task_config['source'])
            analyzer = self.create_analyzer(task_config['analyzer'])
            
            # 准备元数据
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            metadata = {
                'task_name': task_name,
                'run_id': run_id,
                'timestamp': timestamp,
                'created_at': datetime.now().isoformat()
            }
            analyzer.set_metadata(metadata)
            
            sinks = self.create_sinks(task_config.get('sinks', []))
            
            # 执行流程：收集 -> 分析 -> 保存
            logger.info("步骤1: 收集数据库信息...")
            try:
                data = source.collect()
            except ConnectionError as e:
                # 数据库连接失败，直接返回错误报告，不调用分析器
                logger.error(f"数据库连接失败: {e}")
                run_info['status'] = 'failed'
                run_info['stage'] = 'failed'
                run_info['progress'] = {'percentage': 0, 'stage': 'failed'}
                run_info['finished_at'] = datetime.now().isoformat()
                run_info['error'] = str(e)
                
                # 创建错误报告
                from db_ops_analyzer.plugins.analyzers.langgraph import LangGraphAnalyzer
                error_data = {
                    'database_type': task_config['source'].get('name', 'Unknown').title(),
                    'host': task_config['source'].get('params', {}).get('host', 'Unknown'),
                    'port': task_config['source'].get('params', {}).get('port', 'Unknown'),
                    'database': task_config['source'].get('params', {}).get('database', 'Unknown'),
                    'slow_queries': [],
                    'processlist': [],
                    'tables': [],
                    'errors': [str(e)]
                }
                # 创建一个临时分析器来格式化错误报告
                temp_analyzer = self.create_analyzer(task_config.get('analyzer', {}))
                temp_analyzer.set_metadata(metadata)
                result = temp_analyzer._format_error_report(f"数据库连接失败: {str(e)}", error_data)
                
                # 保存错误报告
                report_key = f"{timestamp}_{task_name}"
                self.reports[report_key] = {
                    'id': report_key,
                    'run_id': run_id,
                    'task_name': task_name,
                    'database': error_data.get('database', 'all'),
                    'content': result,
                    'created_at': datetime.now().isoformat(),
                    'timestamp': timestamp
                }
                run_info['report_id'] = report_key
                
                # 保存到sink
                sinks = self.create_sinks(task_config.get('sinks', []))
                for sink in sinks:
                    try:
                        sink.save(result, metadata)
                    except Exception as sink_error:
                        logger.error(f"Sink保存失败: {sink_error}", exc_info=True)
                
                return
            
            # 更新状态：分析数据
            run_info['stage'] = 'analyzing'
            run_info['progress'] = {'percentage': 50, 'stage': 'analyzing'}
            logger.info("步骤2: 分析数据...")
            result = analyzer.analyze(data)
            
            # 更新状态：保存结果
            run_info['stage'] = 'saving'
            run_info['progress'] = {'percentage': 90, 'stage': 'saving'}
            logger.info("步骤3: 保存结果...")
            for sink in sinks:
                try:
                    sink.save(result, metadata)
                except Exception as e:
                    logger.error(f"Sink保存失败: {e}", exc_info=True)
            
            # 创建报告记录
            report_key = f"{timestamp}_{task_name}"
            
            # 从数据中提取数据库信息
            database_name = 'all'
            if isinstance(data, dict):
                database_name = data.get('database', 'all')
            
            self.reports[report_key] = {
                'id': report_key,
                'run_id': run_id,
                'task_name': task_name,
                'database': database_name,
                'content': result,
                'created_at': datetime.now().isoformat(),
                'timestamp': timestamp
            }
            
            # 更新运行状态
            run_info['status'] = 'completed'
            run_info['stage'] = 'finished'
            run_info['progress'] = {'percentage': 100, 'stage': 'finished'}
            run_info['finished_at'] = datetime.now().isoformat()
            run_info['report_id'] = report_key
            
            logger.info(f"任务执行完成: {task_name} (Run ID: {run_id})")
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)
            run_info['status'] = 'failed'
            run_info['stage'] = 'failed'
            run_info['progress'] = {'percentage': 0, 'stage': 'failed'}
            run_info['finished_at'] = datetime.now().isoformat()
            run_info['error'] = str(e)
    
    def execute_task_async(self, task_name: str, override_config: Optional[Dict[str, Any]] = None) -> int:
        """异步执行任务"""
        task_config = override_config or self.config.get_task(task_name)
        if not task_config:
            raise ValueError(f"任务不存在: {task_name}")
        
        run_id = self._create_run(task_name)
        t = threading.Thread(target=self._run_task, args=(run_id, task_name, task_config), daemon=True)
        t.start()
        return run_id
    
    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """获取运行信息"""
        return self.runs.get(run_id)
    
    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """获取报告"""
        return self.reports.get(report_id)
    
    def list_reports(self, database: Optional[str] = None, start_time: Optional[str] = None, 
                     end_time: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """列出报告，支持按数据库和时间过滤"""
        reports = []
        for key, report in self.reports.items():
            # 跳过run_id格式的重复项
            if key.isdigit():
                continue
            
            # 过滤数据库
            if database and report.get('database') != database:
                continue
            
            # 过滤时间范围
            created_at = report.get('created_at', '')
            if start_time and created_at < start_time:
                continue
            if end_time and created_at > end_time:
                continue
            
            reports.append({
                'id': report['id'],
                'run_id': report['run_id'],
                'task_name': report.get('task_name'),
                'database': report.get('database', 'all'),
                'created_at': report.get('created_at'),
                'timestamp': report.get('timestamp')
            })
        
        # 按时间倒序排列
        reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # 限制返回数量
        if limit and limit > 0:
            reports = reports[:limit]
        
        return reports
