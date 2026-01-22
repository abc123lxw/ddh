"""FastAPI服务器"""

import logging
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from log_analyzer.config import Config
from log_analyzer.task import TaskExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 全局配置和执行器
config = None
executor = None
monitoring_thread = None
monitoring_enabled = False


def monitoring_worker():
    """后台监控工作线程 - 每天生成一次汇总报告"""
    global config, executor, monitoring_enabled
    
    while monitoring_enabled:
        try:
            monitoring_config = config.get_monitoring_config()
            if not monitoring_config or not monitoring_config.get('enabled', False):
                time.sleep(3600)  # 如果未启用，等待1小时后重试
                continue
            
            report_interval = monitoring_config.get('report_interval', 86400)  # 默认1天
            containers = monitoring_config.get('containers', [])
            hours_ago = monitoring_config.get('hours_ago', 24)  # 默认分析最近24小时
            report_hour = monitoring_config.get('report_hour', 2)  # 默认凌晨2点
            
            # 如果没有配置容器列表，从任务配置中获取
            if not containers:
                task_config = config.get_task('Apps_Error_Analysis')
                if task_config and 'source' in task_config:
                    source_params = task_config['source'].get('params', {})
                    if 'sources' in source_params:
                        containers = [s.get('container_name') for s in source_params['sources'] 
                                     if s.get('type') == 'docker' and s.get('container_name')]
            
            if not containers:
                logger.warning("监控配置中没有容器列表，跳过本次报告生成")
                time.sleep(report_interval)
                continue
            
            # 计算下次报告生成时间（指定的小时）
            now = datetime.now()
            next_report_time = now.replace(hour=report_hour, minute=0, second=0, microsecond=0)
            if next_report_time <= now:
                # 如果今天的时间已过，设置为明天
                from datetime import timedelta
                next_report_time += timedelta(days=1)
            
            wait_seconds = (next_report_time - now).total_seconds()
            logger.info(f"下次报告生成时间: {next_report_time.strftime('%Y-%m-%d %H:%M:%S')} (等待 {wait_seconds/3600:.1f} 小时)")
            
            # 等待到指定时间
            time.sleep(min(wait_seconds, report_interval))
            
            # 生成报告
            logger.info(f"开始生成每日汇总报告: {containers} (最近{hours_ago}小时)")
            
            # 对所有容器生成汇总报告
            import copy
            task_name = 'Apps_Error_Analysis'
            task_config = config.get_task(task_name)
            if not task_config:
                logger.warning(f"任务 {task_name} 不存在，跳过报告生成")
                continue
            
            temp_config = copy.deepcopy(task_config)
            # 修改为分析所有容器，使用最近N小时
            if 'source' in temp_config and 'params' in temp_config['source']:
                source_params = temp_config['source']['params']
                if 'sources' in source_params:
                    # 更新所有容器的hours_ago
                    for source in source_params['sources']:
                        if source.get('type') == 'docker':
                            source['hours_ago'] = hours_ago
                            source.pop('minutes_ago', None)  # 移除minutes_ago，使用hours_ago
            
            # 生成汇总报告（不指定container_name，分析所有容器）
            run_id = executor.execute_task_async(
                task_name,
                override_config=temp_config,
                container_name=None  # None表示分析所有容器
            )
            logger.info(f"每日汇总报告任务已启动: run_id={run_id}")
            
            # 报告生成后，继续循环等待下一次报告时间
            # 下次循环会重新计算下次报告时间
            
        except Exception as e:
            logger.error(f"监控线程异常: {e}", exc_info=True)
            time.sleep(3600)  # 出错后等待1小时再重试


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global config, executor, monitoring_thread, monitoring_enabled
    
    # 启动时初始化
    try:
        config = Config()
        executor = TaskExecutor(config)
        logger.info("服务器启动成功")
        
        # 启动自动监控
        monitoring_config = config.get_monitoring_config()
        if monitoring_config and monitoring_config.get('enabled', False):
            monitoring_enabled = True
            monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
            monitoring_thread.start()
            logger.info("自动监控已启动")
        else:
            logger.info("自动监控未启用")
            
    except Exception as e:
        logger.error(f"服务器启动失败: {e}", exc_info=True)
        raise
    
    yield
    
    # 关闭时清理
    monitoring_enabled = False
    if monitoring_thread:
        monitoring_thread.join(timeout=5)
    logger.info("服务器已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Log Analyzer API",
    description="基于插件的智能日志分析工具，支持自动化调用大模型进行运维巡查",
    version="0.1.1",
    lifespan=lifespan
)
# 简易前端页面：访问 /ui 即可
app.mount("/ui", StaticFiles(directory="static", html=True), name="ui")


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy", "version": "0.1.1"}


@app.get("/api/tasks")
async def list_tasks():
    """列出所有任务"""
    if not config:
        raise HTTPException(status_code=500, detail="配置未初始化")
    
    tasks = config.get_tasks()
    return {
        "tasks": [
            {
                "name": task.get("name"),
                "source": task.get("source", {}).get("name"),
                "analyzer": task.get("analyzer", {}).get("name"),
                "sinks": [s.get("name") for s in task.get("sinks", [])]
            }
            for task in tasks
        ]
    }


@app.post("/api/tasks/{task_name}/run")
async def run_task(
    task_name: str,
    minutes_ago: Optional[int] = Query(None, description="查询最近N分钟的日志（优先级最高）"),
    hours_ago: Optional[int] = Query(None, description="查询最近N小时的日志（如果未指定minutes_ago）"),
    tail: Optional[int] = Query(None, description="每个容器日志尾部行数上限（默认5000，最大50000）"),
    max_lines: Optional[int] = Query(None, description="额外的日志总行数上限"),
    max_bytes: Optional[int] = Query(None, description="日志总字节上限"),
    chunk_size: Optional[int] = Query(None, description="LLM分块大小（字符），可用于大日志降采样"),
    concurrency: Optional[int] = Query(None, description="LLM并发数，用于控制资源"),
    container_name: Optional[str] = Query(None, description="仅分析指定容器（覆盖任务中的 sources）"),
    since: Optional[str] = Query(None, description="自定义开始时间，格式 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS"),
    until: Optional[str] = Query(None, description="自定义结束时间，格式同上")
):
    """
    触发任务执行
    
    参数:
    - task_name: 任务名称
    - minutes_ago: 可选，查询最近N分钟的日志（优先级最高）
    - hours_ago: 可选，查询最近N小时的日志（如果未指定minutes_ago）
    """
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    try:
        # 创建临时任务配置
        import copy
        task_config = executor.config.get_task(task_name)
        if not task_config:
            raise ValueError(f"任务不存在: {task_name}")
        
        temp_config = copy.deepcopy(task_config)
        
        # 修改source配置中的时间/限流参数
        if 'source' in temp_config and 'params' in temp_config['source']:
            source_params = temp_config['source']['params']
            if 'sources' in source_params:
                if container_name:
                    # 覆盖为单个容器
                    source_params['sources'] = [{
                        "type": "docker",
                        "container_name": container_name,
                        "minutes_ago": minutes_ago,
                        "hours_ago": hours_ago,
                        "tail": tail,
                        "max_lines": max_lines,
                        "max_bytes": max_bytes,
                        "since": since,
                        "until": until
                    }]
                else:
                    for source in source_params['sources']:
                        if source.get('type') == 'docker':
                            if minutes_ago is not None:
                                source['minutes_ago'] = minutes_ago
                                source.pop('hours_ago', None)
                            elif hours_ago is not None:
                                source['hours_ago'] = hours_ago
                                source.pop('minutes_ago', None)
                            if tail is not None:
                                source['tail'] = tail
                            if max_lines is not None:
                                source['max_lines'] = max_lines
                            if max_bytes is not None:
                                source['max_bytes'] = max_bytes
                            if since is not None:
                                source['since'] = since
                            if until is not None:
                                source['until'] = until
        
        # 修改 analyzer 的分块/并发
        if 'analyzer' in temp_config and 'params' in temp_config['analyzer']:
            analyzer_params = temp_config['analyzer']['params']
            if chunk_size is not None:
                analyzer_params['chunk_size'] = chunk_size
            if concurrency is not None:
                analyzer_params['concurrency'] = concurrency

        # 异步后台执行（立即返回run_id）
        run_id = executor.execute_task_async(task_name, override_config=temp_config, container_name=container_name)
        
        return {
            "message": "任务已启动",
            "run_id": run_id,
            "task_name": task_name,
            "container_name": container_name or "all",
            "time_range": {
                "minutes_ago": minutes_ago,
                "hours_ago": hours_ago if minutes_ago is None else None,
                "since": since,
                "until": until
            },
            "limits": {
                "tail": tail,
                "max_lines": max_lines,
                "max_bytes": max_bytes,
                "chunk_size": chunk_size,
                "concurrency": concurrency
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}")
async def get_run(run_id: int):
    """查询任务运行状态"""
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    run_info = executor.get_run(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail=f"运行记录不存在: {run_id}")
    
    return run_info


@app.get("/api/reports/{report_id}")
async def get_report(report_id: Any):
    """获取分析报告（支持run_id或时间_容器名格式）"""
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    report = executor.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
    
    # 返回报告内容（Markdown格式）
    from fastapi.responses import Response
    return Response(
        content=report.get('content', ''),
        media_type='text/markdown; charset=utf-8'
    )


@app.get("/api/reports")
async def list_reports(
    container_name: Optional[str] = Query(None, description="按容器名称过滤"),
    start_time: Optional[str] = Query(None, description="开始时间（ISO格式）"),
    end_time: Optional[str] = Query(None, description="结束时间（ISO格式）"),
    limit: Optional[int] = Query(None, description="限制返回数量（例如：最近10个报告）")
):
    """列出所有报告，支持按容器名称和时间过滤，支持限制数量"""
    if not executor:
        raise HTTPException(status_code=500, detail="执行器未初始化")
    
    reports = executor.list_reports(container_name, start_time, end_time, limit)
    return {"reports": reports}


@app.get("/api/monitoring/status")
async def get_monitoring_status():
    """获取自动监控状态"""
    if not config:
        raise HTTPException(status_code=500, detail="配置未初始化")
    
    monitoring_config = config.get_monitoring_config() or {}
    report_interval = monitoring_config.get('report_interval', 86400)
    report_hour = monitoring_config.get('report_hour', 2)
    
    # 计算下次报告时间
    now = datetime.now()
    next_report_time = now.replace(hour=report_hour, minute=0, second=0, microsecond=0)
    if next_report_time <= now:
        from datetime import timedelta
        next_report_time += timedelta(days=1)
    
    return {
        "enabled": monitoring_enabled and (monitoring_config.get('enabled', False)),
        "report_interval": report_interval,
        "report_interval_hours": report_interval / 3600,
        "report_hour": report_hour,
        "next_report_time": next_report_time.isoformat(),
        "containers": monitoring_config.get('containers', []),
        "hours_ago": monitoring_config.get('hours_ago', 24)
    }


if __name__ == "__main__":
    import uvicorn
    # 从配置读取端口
    try:
        cfg = Config()
        server_config = cfg.server
        port = server_config.get('port', 8001)
        host = server_config.get('host', '0.0.0.0')
    except Exception:
        # 如果配置加载失败，使用默认值
        port = 8001
        host = '0.0.0.0'
    uvicorn.run(app, host=host, port=port)
