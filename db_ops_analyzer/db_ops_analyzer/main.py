"""命令行入口"""

import argparse
import logging
import sys
from db_ops_analyzer.config import Config
from db_ops_analyzer.task import TaskExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库运维分析工具")
    parser.add_argument("--task", type=str, help="任务名称")
    parser.add_argument("--config", type=str, help="配置文件路径", default="config.yaml")
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = Config(args.config)
        executor = TaskExecutor(config)
        
        if args.task:
            # 执行指定任务
            logger.info(f"执行任务: {args.task}")
            run_id = executor.execute_task_async(args.task)
            logger.info(f"任务已启动，Run ID: {run_id}")
            
            # 等待任务完成
            import time
            while True:
                run = executor.get_run(run_id)
                if not run:
                    logger.error("运行记录不存在")
                    sys.exit(1)
                
                status = run.get('status')
                if status == 'completed':
                    logger.info("任务执行完成")
                    report_id = run.get('report_id')
                    if report_id:
                        report = executor.get_report(report_id)
                        if report:
                            print("\n" + "="*80)
                            print("分析报告:")
                            print("="*80)
                            print(report.get('content', ''))
                    break
                elif status == 'failed':
                    logger.error(f"任务执行失败: {run.get('error')}")
                    sys.exit(1)
                
                time.sleep(2)
        else:
            # 列出所有任务
            tasks = config.get_tasks()
            print("可用任务:")
            for task in tasks:
                print(f"  - {task.get('name')}")
    
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
