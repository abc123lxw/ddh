"""命令行入口"""

import sys
import logging
import argparse
from log_analyzer.config import Config
from log_analyzer.task import TaskExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="日志分析工具")
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='配置文件路径'
    )
    parser.add_argument(
        '--task',
        type=str,
        help='要执行的任务名称（如果指定了--container，则不需要）'
    )
    parser.add_argument(
        '--container',
        type=str,
        help='要分析的容器名称（单个服务）'
    )
    parser.add_argument(
        '--minutes-ago',
        type=int,
        help='查询最近N分钟的日志'
    )
    parser.add_argument(
        '--hours-ago',
        type=int,
        help='查询最近N小时的日志'
    )
    parser.add_argument(
        '--since',
        type=str,
        help='开始时间（格式：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS）'
    )
    parser.add_argument(
        '--until',
        type=str,
        help='结束时间（格式：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS）'
    )
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = Config(args.config)
        
        # 创建执行器
        executor = TaskExecutor(config)
        
        # 如果指定了container，创建临时任务配置
        if args.container:
            import copy
            import os
            
            # 使用默认任务作为模板，或创建一个新任务
            base_task_name = args.task or 'Apps_Error_Analysis'
            base_task = config.get_task(base_task_name)
            
            if not base_task:
                # 创建一个简单的任务配置
                base_task = {
                    'name': f'custom_{args.container}',
                    'source': {
                        'name': 'docker',
                        'params': {
                            'container_name': args.container
                        }
                    },
                    'analyzer': {
                        'name': 'langgraph',
                        'params': {
                            'base_url': os.getenv('LLM_BASE_URL', 'http://10.163.25.156:5024/v1'),
                            'api_key': os.getenv('LLM_API_KEY', 'zhipu2025ddh'),
                            'model_name': os.getenv('LLM_MODEL_NAME', 'external-ds-v3_2'),
                            'mode': 'sequential',
                            'concurrency': 3
                        }
                    },
                    'sinks': [{
                        'name': 'file',
                        'params': {
                            'output_path': f'reports/{args.container}_{{timestamp}}.md'
                        }
                    }]
                }
            else:
                base_task = copy.deepcopy(base_task)
            
            # 修改容器名称和时间参数
            if base_task['source']['name'] == 'multi':
                # MultiSource需要修改sources列表
                sources = base_task['source']['params'].get('sources', [])
                # 只保留匹配的容器，或创建新的
                base_task['source']['params']['sources'] = [{
                    'type': 'docker',
                    'container_name': args.container,
                    'label': args.container
                }]
            else:
                # 单个Docker源
                base_task['source']['params']['container_name'] = args.container
            
            # 设置时间参数
            if args.minutes_ago:
                if base_task['source']['name'] == 'multi':
                    for source in base_task['source']['params']['sources']:
                        source['minutes_ago'] = args.minutes_ago
                        source.pop('hours_ago', None)
                else:
                    base_task['source']['params']['minutes_ago'] = args.minutes_ago
                    base_task['source']['params'].pop('hours_ago', None)
            elif args.hours_ago:
                if base_task['source']['name'] == 'multi':
                    for source in base_task['source']['params']['sources']:
                        source['hours_ago'] = args.hours_ago
                        source.pop('minutes_ago', None)
                else:
                    base_task['source']['params']['hours_ago'] = args.hours_ago
                    base_task['source']['params'].pop('minutes_ago', None)
            
            if args.since:
                if base_task['source']['name'] == 'multi':
                    for source in base_task['source']['params']['sources']:
                        source['since'] = args.since
                else:
                    base_task['source']['params']['since'] = args.since
            
            if args.until:
                if base_task['source']['name'] == 'multi':
                    for source in base_task['source']['params']['sources']:
                        source['until'] = args.until
                else:
                    base_task['source']['params']['until'] = args.until
            
            # 执行临时任务
            task_name = f'custom_{args.container}'
            logger.info(f"执行自定义任务: 容器={args.container}, 时间范围={args.minutes_ago or args.hours_ago or '默认'}")
            run_id = executor.execute_task(task_name, override_config=base_task)
        else:
            # 使用配置的任务
            if not args.task:
                parser.error("必须指定 --task 或 --container")
            
            # 如果指定了时间范围，修改任务配置
            if args.minutes_ago or args.hours_ago or args.since or args.until:
                import copy
                task_config = copy.deepcopy(config.get_task(args.task))
                if not task_config:
                    raise ValueError(f"任务不存在: {args.task}")
                
                # 修改时间参数
                if 'source' in task_config and 'params' in task_config['source']:
                    source_params = task_config['source']['params']
                    if 'sources' in source_params:
                        for source in source_params['sources']:
                            if source.get('type') == 'docker':
                                if args.minutes_ago:
                                    source['minutes_ago'] = args.minutes_ago
                                    source.pop('hours_ago', None)
                                elif args.hours_ago:
                                    source['hours_ago'] = args.hours_ago
                                    source.pop('minutes_ago', None)
                                if args.since:
                                    source['since'] = args.since
                                if args.until:
                                    source['until'] = args.until
                
                run_id = executor.execute_task(args.task, override_config=task_config)
            else:
                run_id = executor.execute_task(args.task)
        
        logger.info(f"任务执行完成，运行ID: {run_id}")
        
        # 获取运行信息
        run_info = executor.get_run(run_id)
        if run_info:
            print(f"\n运行状态: {run_info['status']}")
            if run_info.get('report_id'):
                print(f"报告ID: {run_info['report_id']}")
                if isinstance(run_info['report_id'], str) and run_info['report_id'].endswith('.md'):
                    print(f"报告文件: {run_info['report_id']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
