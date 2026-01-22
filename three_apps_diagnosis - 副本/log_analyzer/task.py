"""任务执行引擎"""

import logging
import importlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from log_analyzer.config import Config
from log_analyzer.plugins.sources import AbstractSource
from log_analyzer.plugins.analyzers import AbstractAnalyzer
from log_analyzer.plugins.sinks import AbstractSink

logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, config: Config):
        """
        初始化任务执行器
        
        Args:
            config: 配置对象
        """
        import threading

        self.config = config
        self.runs: Dict[int, Dict[str, Any]] = {}
        self.reports: Dict[str, Dict[str, Any]] = {}  # 改为字符串key: 时间_容器名
        self._run_id_counter = 0
        self._lock = threading.Lock()
    
    def create_source(self, source_config: Dict[str, Any]) -> AbstractSource:
        """创建Source插件实例"""
        source_name = source_config.get('name')
        source_params = source_config.get('params', {})
        
        # 动态导入插件
        try:
            if source_name == 'multi':
                from log_analyzer.plugins.sources.multi import MultiSource
                return MultiSource(**source_params)
            elif source_name == 'docker':
                from log_analyzer.plugins.sources.docker import DockerSource
                return DockerSource(**source_params)
            elif source_name == 'file':
                from log_analyzer.plugins.sources.file import FileSource
                return FileSource(**source_params)
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
                from log_analyzer.plugins.analyzers.langgraph import LangGraphAnalyzer
                # 传递进度回调
                analyzer_params['progress_callback'] = self._update_progress
                return LangGraphAnalyzer(**analyzer_params)
            else:
                raise ValueError(f"未知的Analyzer插件: {analyzer_name}")
        except Exception as e:
            logger.error(f"创建Analyzer插件失败: {e}", exc_info=True)
            raise
    
    def create_sinks(self, sinks_config: List[Dict[str, Any]]) -> List[AbstractSink]:
        """创建Sink插件实例列表"""
        sinks = []
        for sink_config in sinks_config:
            sink_name = sink_config.get('name')
            sink_params = sink_config.get('params', {})
            
            try:
                if sink_name == 'database':
                    from log_analyzer.plugins.sinks.database import DatabaseSink
                    sinks.append(DatabaseSink(**sink_params))
                elif sink_name == 'file':
                    from log_analyzer.plugins.sinks.file import FileSink
                    sinks.append(FileSink(**sink_params))
                elif sink_name == 'minio':
                    from log_analyzer.plugins.sinks.minio import MinIOSink
                    sinks.append(MinIOSink(**sink_params))
                else:
                    logger.warning(f"未知的Sink插件: {sink_name}，跳过")
            except Exception as e:
                logger.error(f"创建Sink插件失败: {e}", exc_info=True)
        
        return sinks
    
    def _update_progress(self, run_id: int, total_chunks: int, processed_chunks: int):
        """更新进度信息"""
        if run_id in self.runs:
            percentage = int((processed_chunks / total_chunks * 100)) if total_chunks > 0 else 0
            self.runs[run_id]['progress'] = {
                'total_chunks': total_chunks,
                'processed_chunks': processed_chunks,
                'percentage': percentage
            }
            logger.debug(f"进度更新: run_id={run_id}, {processed_chunks}/{total_chunks} ({percentage}%)")
    
    def _create_run(self, task_name: str, container_name: Optional[str] = None) -> int:
        """内部方法：创建run记录并返回run_id"""
        with self._lock:
            run_id = self._run_id_counter + 1
            self._run_id_counter = run_id
        run_info = {
            'id': run_id,
            'task_name': task_name,
            'container_name': container_name or 'all',
            'status': 'running',
            'stage': 'queued',
            'started_at': datetime.now().isoformat(),
            'finished_at': None,
            'error': None,
            'progress': {
                'total_chunks': 0,
                'processed_chunks': 0,
                'percentage': 0
            }
        }
        self.runs[run_id] = run_info
        return run_id

    def _run_task(self, run_id: int, task_name: str, task_config: Dict[str, Any], container_name: Optional[str] = None):
        """实际执行任务（在后台线程中调用）"""
        run_info = self.runs[run_id]
        try:
            logger.info(f"开始执行任务: {task_name} (Run ID: {run_id})")
            run_info['stage'] = 'collecting'
            run_info['progress'] = {'total_chunks': 0, 'processed_chunks': 0, 'percentage': 0}
            
            # 创建插件实例
            source = self.create_source(task_config['source'])
            analyzer = self.create_analyzer(task_config['analyzer'])
            # 传递run_id给analyzer用于进度更新
            if hasattr(analyzer, 'set_run_id'):
                analyzer.set_run_id(run_id)
            
            sinks = self.create_sinks(task_config.get('sinks', []))
            
            # 执行流程：收集 -> 分析 -> 保存
            logger.info("步骤1: 收集数据...")
            data = source.collect()
            
            # 如果data是迭代器，转换为字符串
            if hasattr(data, '__iter__') and not isinstance(data, str):
                data = '\n'.join(data)
            
            run_info['stage'] = 'analyzing'
            logger.info("步骤2: 分析数据...")
            result = analyzer.analyze(data)
            
            run_info['stage'] = 'saving'
            logger.info("步骤3: 保存结果...")
            sink_result = None
            minio_path = None
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            container = container_name or run_info.get('container_name', 'all')
            
            metadata = {
                'task_name': task_name,
                'run_id': run_id,
                'container_name': container,
                'timestamp': timestamp,
                'created_at': datetime.now().isoformat()
            }
            
            for sink in sinks:
                try:
                    result_path = sink.save(result, metadata)
                    if result_path:
                        if not sink_result:
                            sink_result = result_path
                        # 检查是否是MinIO路径
                        if 'minio' in str(type(sink)).lower() or '/' in result_path:
                            minio_path = result_path
                except Exception as e:
                    logger.error(f"Sink保存失败: {e}", exc_info=True)
            
            # 创建报告记录（使用时间_容器名作为key）
            report_key = f"{timestamp}_{container}"
            self.reports[report_key] = {
                'id': report_key,
                'run_id': run_id,
                'task_name': task_name,
                'container_name': container,
                'content': result,
                'file_path': sink_result,
                'minio_path': minio_path,
                'created_at': datetime.now().isoformat(),
                'timestamp': timestamp
            }
            
            # 同时用run_id也能查到
            self.reports[str(run_id)] = self.reports[report_key]
            
            # 更新运行状态
            run_info['status'] = 'completed'
            run_info['finished_at'] = datetime.now().isoformat()
            run_info['report_id'] = report_key
            run_info['stage'] = 'finished'
            run_info['progress']['percentage'] = 100
            
            logger.info(f"任务执行完成: {task_name} (Run ID: {run_id}, Report Key: {report_key})")
        except Exception as e:
            logger.error(f"任务执行失败: {e}", exc_info=True)
            run_info['status'] = 'failed'
            run_info['finished_at'] = datetime.now().isoformat()
            run_info['error'] = str(e)
            run_info['stage'] = 'failed'

    def execute_task_async(self, task_name: str, override_config: Optional[Dict[str, Any]] = None, container_name: Optional[str] = None) -> int:
        """
        异步执行任务：立即返回run_id，在后台线程中处理
        """
        import threading

        task_config = override_config or self.config.get_task(task_name)
        if not task_config:
            raise ValueError(f"任务不存在: {task_name}")
        
        run_id = self._create_run(task_name, container_name)
        t = threading.Thread(target=self._run_task, args=(run_id, task_name, task_config, container_name), daemon=True)
        t.start()
        return run_id
    
    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """获取运行信息"""
        return self.runs.get(run_id)
    
    def get_report(self, report_id: Any) -> Optional[Dict[str, Any]]:
        """获取报告（支持run_id或时间_容器名格式）"""
        # 先尝试直接查找
        report = self.reports.get(str(report_id))
        if report:
            return report
        # 如果不存在，返回None
        return None
    
    def list_reports(self, container_name: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """列出报告，支持按容器名称和时间过滤，支持限制数量"""
        reports = []
        for key, report in self.reports.items():
            # 跳过run_id格式的重复项
            if key.isdigit():
                continue
            
            # 过滤容器名称
            if container_name and report.get('container_name') != container_name:
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
                'container_name': report.get('container_name', 'all'),
                'task_name': report.get('task_name'),
                'created_at': report.get('created_at'),
                'timestamp': report.get('timestamp'),
                'minio_path': report.get('minio_path')
            })
        
        # 按时间倒序排列
        reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # 限制返回数量
        if limit and limit > 0:
            reports = reports[:limit]
        
        return reports
