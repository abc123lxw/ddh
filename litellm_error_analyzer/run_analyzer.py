"""
LiteLLM 错误日志分析工具 - 主运行脚本
从 config.py 读取所有配置并执行分析
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json

# 设置控制台输出编码为 UTF-8（解决 Windows 中文乱码问题）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 导入分析模块
from jupyter_error_analyzer import analyze_errors, query_errors, prepare_for_llm, call_llm_api


def load_config():
    """从 config.py 加载配置"""
    try:
        from config import (
            POSTGRES_CONFIG,
            QUERY_CONFIG,
            LLM_CONFIG,
            OUTPUT_CONFIG
        )
        return {
            'db': POSTGRES_CONFIG,
            'query': QUERY_CONFIG,
            'llm': LLM_CONFIG,
            'output': OUTPUT_CONFIG
        }
    except ImportError as e:
        print(f"❌ 无法导入配置文件: {e}")
        print("请确保 config.py 文件存在且配置正确")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        sys.exit(1)


def parse_time(time_str: Optional[str]) -> Optional[datetime]:
    """解析时间字符串"""
    if time_str is None:
        return None
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        print(f"⚠️  时间格式错误: {time_str}，应使用格式: YYYY-MM-DD HH:MM:SS")
        return None


def ensure_output_dir(output_dir: str):
    """确保输出目录存在"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        return True
    except Exception as e:
        print(f"⚠️  无法创建输出目录 {output_dir}: {e}")
        return False


def save_results(
    error_logs: List[Dict],
    analysis_logs: List[Dict],
    llm_result: Optional[str],
    config: Dict
):
    """保存分析结果到文件（按日期创建目录）"""
    base_output_dir = config['output']['output_dir']
    
    # 创建按日期命名的目录（格式: YYYY-MM-DD）
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = os.path.join(base_output_dir, today)
    
    if not ensure_output_dir(output_dir):
        print(f"⚠️  无法创建输出目录 {output_dir}，将使用当前目录保存结果")
        output_dir = "."
    
    # 显示输出目录（无论是否创建成功）
    abs_output_dir = os.path.abspath(output_dir)
    print(f"📁 输出目录: {abs_output_dir}")
    
    timestamp = datetime.now().strftime("%H%M%S")
    
    # 保存完整错误日志
    if config['output']['save_full_logs']:
        full_logs_file = os.path.join(output_dir, f"error_logs_full_{timestamp}.json")
        try:
            with open(full_logs_file, 'w', encoding='utf-8') as f:
                json.dump(error_logs, f, ensure_ascii=False, indent=2, default=str)
            print(f"✅ 完整错误日志已保存: {full_logs_file}")
        except Exception as e:
            print(f"⚠️  保存完整日志失败: {e}")
    
    # 保存分析日志
    if config['output']['save_analysis_logs']:
        analysis_file = os.path.join(output_dir, f"error_logs_analysis_{timestamp}.json")
        try:
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_logs, f, ensure_ascii=False, indent=2, default=str)
            print(f"✅ 分析日志已保存: {analysis_file}")
        except Exception as e:
            print(f"⚠️  保存分析日志失败: {e}")
    
    # 保存 LLM 分析结果
    if llm_result and config['output']['save_llm_result']:
        llm_result_file = os.path.join(output_dir, f"llm_analysis_{timestamp}.txt")
        try:
            with open(llm_result_file, 'w', encoding='utf-8', errors='replace') as f:
                f.write(llm_result)
            print(f"✅ LLM 分析结果已保存: {llm_result_file}")
        except Exception as e:
            print(f"⚠️  保存 LLM 结果失败: {e}")
    elif config['output']['save_llm_result'] and not llm_result:
        # 如果启用了 LLM 但结果为空，也记录一下
        print("ℹ️  LLM 分析结果为空，未保存")
    
    # 保存查询参数（用于记录本次查询的参数）
    try:
        query_params_file = os.path.join(output_dir, f"query_params_{timestamp}.json")
        query_params = {
            'query_time': datetime.now().isoformat(),
            'error_logs_count': len(error_logs),
            'analysis_logs_count': len(analysis_logs),
            'has_llm_result': llm_result is not None,
            'config': {
                'query': config.get('query', {}),
                'db': {k: v for k, v in config.get('db', {}).items() if k != 'password'}  # 不保存密码
            }
        }
        with open(query_params_file, 'w', encoding='utf-8') as f:
            json.dump(query_params, f, ensure_ascii=False, indent=2, default=str)
        print(f"✅ 查询参数已保存: {query_params_file}")
    except Exception as e:
        print(f"⚠️  保存查询参数失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("LiteLLM 错误日志分析工具")
    print("=" * 60)
    
    # 1. 加载配置
    print("\n[1/4] 加载配置...")
    config = load_config()
    print("✅ 配置加载成功")
    
    # 2. 解析查询参数
    print("\n[2/4] 解析查询参数...")
    query_config = config['query']
    
    # 检查是否使用时间筛选
    use_time_filter = query_config.get('use_time_filter', True)
    
    # 处理时间范围
    if use_time_filter:
        start_time = parse_time(query_config.get('start_time'))
        end_time = parse_time(query_config.get('end_time'))
        
        # 如果时间范围都未指定，使用 days_back
        if start_time is None and end_time is None:
            days_back = query_config.get('days_back', 7)
            if days_back is not None:
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days_back)
                print(f"   使用默认时间范围: 最近 {days_back} 天")
            else:
                print("   ⚠️  时间筛选已启用，但未指定时间范围且 days_back 为 None")
                start_time = None
                end_time = None
        else:
            print(f"   时间范围: {start_time} 到 {end_time}")
    else:
        start_time = None
        end_time = None
        print("   ⏭️  跳过时间范围筛选（use_time_filter=False）")
    
    # 显示筛选条件
    if query_config.get('key_name'):
        print(f"   Key Alias/Name: {query_config['key_name']}")
    if query_config.get('model'):
        print(f"   Model: {query_config['model']}")
    print(f"   限制条数: {query_config.get('limit', 100)}")
    
    # 3. 查询错误日志
    print("\n[3/4] 查询错误日志...")
    try:
        # 构建数据库配置（包含查询配置中的 use_time_filter 和 days_back）
        db_config_with_query = config['db'].copy()
        db_config_with_query['use_time_filter'] = use_time_filter
        db_config_with_query['days_back'] = query_config.get('days_back')
        
        error_logs = query_errors(
            start_time=start_time,
            end_time=end_time,
            key_name=query_config.get('key_name'),
            model=query_config.get('model'),
            limit=query_config.get('limit', 100),
            db_config=db_config_with_query
        )
        
        if not error_logs:
            print("❌ 未找到错误日志")
            # 即使没有找到日志，也保存空结果（用于记录查询条件）
            analysis_logs = []
            llm_result = None
            save_results([], [], None, config)
            return
        
        print(f"✅ 找到 {len(error_logs)} 条错误日志")
        
        # 准备分析数据
        analysis_logs = prepare_for_llm(error_logs)
        
        # 4. 调用大模型分析（如果启用）
        llm_result = None
        llm_config = config['llm']
        
        if llm_config.get('enabled', False):
            print("\n[4/4] 调用大模型分析...")
            print(f"   正在分析 {len(analysis_logs)} 条日志，可能需要较长时间，请耐心等待...")
            api_url = llm_config.get('api_url')
            api_key = llm_config.get('api_key')
            model = llm_config.get('model', 'gpt-4')
            timeout = llm_config.get('timeout', 600)
            
            if not api_url:
                print("⚠️  LLM 已启用但未配置 API URL，跳过分析")
            else:
                try:
                    llm_result = call_llm_api(
                        analysis_logs,
                        api_url,
                        api_key,
                        model
                    )
                    if llm_result:
                        print("✅ 大模型分析完成")
                        # 打印前500字符
                        preview = llm_result[:500] + "..." if len(llm_result) > 500 else llm_result
                        print(f"\n分析结果预览:\n{preview}")
                except KeyboardInterrupt:
                    print("\n⚠️  用户中断了 LLM 分析")
                    llm_result = None
                except Exception as e:
                    print(f"⚠️  调用大模型失败: {e}")
                    llm_result = None
        else:
            print("\n[4/4] 跳过 LLM 分析（未启用）")
        
        # 5. 保存结果
        print("\n[5/5] 保存结果...")
        save_results(error_logs, analysis_logs, llm_result, config)
        
        # 6. 打印统计摘要
        print("\n" + "=" * 60)
        print("统计摘要")
        print("=" * 60)
        
        # 统计模型
        model_stats = {}
        error_type_stats = {}
        for log in error_logs:
            model = log.get('model', 'Unknown')
            model_stats[model] = model_stats.get(model, 0) + 1
            
            # 提取错误类型
            error_type = log.get('exception_type', '')
            if not error_type:
                metadata = log.get('metadata', {})
                if isinstance(metadata, dict):
                    error_info = metadata.get('error_information', {})
                    error_type = error_info.get('error_class', '')
            if error_type:
                error_type_stats[error_type] = error_type_stats.get(error_type, 0) + 1
        
        print(f"总错误数: {len(error_logs)}")
        if model_stats:
            print("\n按模型统计:")
            for m, count in sorted(model_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"  {m}: {count}")
        if error_type_stats:
            print("\n按错误类型统计:")
            for e, count in sorted(error_type_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"  {e}: {count}")
        
        print("\n" + "=" * 60)
        print("✅ 分析完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 即使出错，也尝试保存错误信息
        try:
            error_info = {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'query_time': datetime.now().isoformat(),
                'config': {
                    'query': config.get('query', {}),
                    'db': {k: v for k, v in config.get('db', {}).items() if k != 'password'}
                }
            }
            base_output_dir = config['output']['output_dir']
            today = datetime.now().strftime("%Y-%m-%d")
            output_dir = os.path.join(base_output_dir, today)
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%H%M%S")
            error_file = os.path.join(output_dir, f"error_{timestamp}.json")
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, ensure_ascii=False, indent=2)
            print(f"\n⚠️  错误信息已保存到: {error_file}")
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()

