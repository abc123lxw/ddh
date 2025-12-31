"""
通过 Docker exec 从 LiteLLM 数据库中查询错误日志
支持筛选条件：时间范围、Key Name、Model
"""

import subprocess
import json
from datetime import datetime
from typing import Optional, List, Dict, Any


class LiteLLMErrorLogQueryDocker:
    def __init__(
        self,
        container_name: str = "litellm-db-bak",
        database: str = "litellm_db",
        user: str = "litellm_user",
        password: str = "zhipu2025ddh"
    ):
        """
        初始化 Docker 容器查询参数
        
        Args:
            container_name: Docker 容器名称
            database: 数据库名称
            user: 用户名
            password: 密码
        """
        self.container_name = container_name
        self.database = database
        self.user = user
        self.password = password
    
    def _execute_sql_json(self, sql: str) -> List[Dict[str, Any]]:
        """
        通过 docker exec 执行 SQL 查询，返回 JSON 格式
        
        Args:
            sql: 基础 SQL 查询语句（不包含 json_agg）
        
        Returns:
            JSON 格式的查询结果列表
        """
        # 修改 SQL，使用 PostgreSQL 的 JSON 聚合功能
        json_sql = f"SELECT json_agg(row_to_json(t)) FROM ({sql}) t;"
        
        psql_cmd = [
            "docker", "exec",
            "-e", f"PGPASSWORD={self.password}",
            self.container_name,
            "psql",
            "-U", self.user,
            "-d", self.database,
            "-t",  # 只输出数据
            "-A",  # 非对齐格式
            "-c", json_sql
        ]
        
        try:
            result = subprocess.run(
                psql_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            output = result.stdout.strip()
            if not output or output == 'null':
                return []
            
            # 解析 JSON
            data = json.loads(output)
            return data if isinstance(data, list) else []
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            print(f"输出内容: {output[:500]}")
            return []
        except subprocess.CalledProcessError as e:
            print(f"❌ SQL 执行失败: {e}")
            print(f"错误输出: {e.stderr}")
            return []
        except Exception as e:
            print(f"❌ 执行出错: {e}")
            return []
    
    def query_error_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        key_name: Optional[str] = None,
        model: Optional[str] = None,
        limit: Optional[int] = None,
        use_error_logs_table: bool = True,
        use_spend_logs_table: bool = True
    ) -> List[Dict[str, Any]]:
        """
        查询错误日志（支持三个筛选条件）
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            key_name: Key Alias/Name 筛选（支持 key_alias、key_name、api_key）
            model: Model 筛选
            limit: 限制条数
            use_error_logs_table: 是否查询 ErrorLogs 表
            use_spend_logs_table: 是否查询 SpendLogs 表
        
        Returns:
            错误日志列表
        """
        all_logs = []
        
        # 查询 ErrorLogs 表
        if use_error_logs_table:
            error_logs = self._query_error_logs_table(
                start_time, end_time, key_name, model, limit
            )
            all_logs.extend(error_logs)
        
        # 查询 SpendLogs 表
        if use_spend_logs_table:
            spend_logs = self._query_spend_logs_table(
                start_time, end_time, key_name, model, limit
            )
            all_logs.extend(spend_logs)
        
        # 去重（基于 request_id）
        unique_logs = {}
        for log in all_logs:
            request_id = log.get('request_id') or log.get('id')
            if request_id and request_id not in unique_logs:
                unique_logs[request_id] = log
        
        unique_logs = list(unique_logs.values())
        
        # 按时间排序
        unique_logs.sort(
            key=lambda x: x.get('startTime', '') or x.get('created_at', ''),
            reverse=True
        )
        
        # 限制条数
        if limit:
            unique_logs = unique_logs[:limit]
        
        return unique_logs
    
    def _query_error_logs_table(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        key_name: Optional[str],
        model: Optional[str],
        limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """
        查询 LiteLLM_ErrorLogs 表
        
        注意：ErrorLogs 表中没有 key 相关字段，所以 key_name 筛选不适用于此表
        如果需要通过 key_alias 筛选，应该查询 SpendLogs 表
        
        筛选条件：
        1. 时间范围：startTime 字段
        2. 模型：litellm_model_name 字段
        """
        # 构建 WHERE 条件
        conditions = []
        
        # 1. 时间范围筛选
        if start_time:
            conditions.append(f'"startTime" >= \'{start_time.isoformat()}\'')
        
        if end_time:
            conditions.append(f'"startTime" <= \'{end_time.isoformat()}\'')
        
        # 2. 模型筛选
        if model:
            conditions.append(f'"litellm_model_name" = \'{model}\'')
        
        # 注意：ErrorLogs 表没有 key 相关字段，无法通过 key_name 筛选
        
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        limit_clause = f' LIMIT {limit}' if limit else ''
        
        # 构建 SQL 查询
        sql = f'''SELECT * FROM "LiteLLM_ErrorLogs" 
WHERE {where_clause}
ORDER BY "startTime" DESC
{limit_clause}'''
        
        result = self._execute_sql_json(sql)
        
        # 为每条记录添加表标识和统一字段名
        for log in result:
            log['_source_table'] = 'LiteLLM_ErrorLogs'
            if 'litellm_model_name' in log:
                log['model'] = log.get('litellm_model_name')
        
        return result
    
    def _query_spend_logs_table(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        key_name: Optional[str],
        model: Optional[str],
        limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """
        查询 LiteLLM_SpendLogs 表（只查询错误状态）
        
        三个筛选条件：
        1. 时间范围：startTime 字段
        2. 模型：model 字段
        3. Key：通过 metadata->user_api_key_alias 字段查询（key_alias 存储在 metadata JSON 中）
        """
        # 构建 WHERE 条件（只查询错误状态）
        conditions = ['"status" != \'success\'', '"status" IS NOT NULL']
        
        # 1. 时间范围筛选
        if start_time:
            conditions.append(f'"startTime" >= \'{start_time.isoformat()}\'')
        
        if end_time:
            conditions.append(f'"startTime" <= \'{end_time.isoformat()}\'')
        
        # 2. 模型筛选
        if model:
            conditions.append(f'"model" = \'{model}\'')
        
        # 3. Key 筛选：key_alias 存储在 metadata->user_api_key_alias 中
        # 注意：需要使用 JSON 操作符 ->'user_api_key_alias' 来访问 JSON 字段
        if key_name:
            # 使用 PostgreSQL JSON 操作符查询 metadata 中的 user_api_key_alias
            # ->'user_api_key_alias' 返回 JSON，->>'user_api_key_alias' 返回文本
            conditions.append(f'metadata->>\'user_api_key_alias\' = \'{key_name}\'')
        
        where_clause = ' AND '.join(conditions)
        limit_clause = f' LIMIT {limit}' if limit else ''
        
        # 构建 SQL 查询
        sql = f'''SELECT * FROM "LiteLLM_SpendLogs" 
WHERE {where_clause}
ORDER BY "startTime" DESC
{limit_clause}'''
        
        result = self._execute_sql_json(sql)
        
        # 为每条记录添加表标识，并从 metadata 中提取 key_alias
        for log in result:
            log['_source_table'] = 'LiteLLM_SpendLogs'
            # 从 metadata 中提取 key_alias 到顶层，方便使用
            if 'metadata' in log and isinstance(log['metadata'], dict):
                if 'user_api_key_alias' in log['metadata']:
                    log['key_alias'] = log['metadata']['user_api_key_alias']
        
        return result


def main():
    """主函数 - 示例用法"""
    query = LiteLLMErrorLogQueryDocker(
        container_name="litellm-db-bak",
        database="litellm_db",
        user="litellm_user",
        password="zhipu2025ddh"
    )
    
    from datetime import timedelta
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    
    print("=" * 60)
    print("LiteLLM 错误日志查询工具 (Docker Exec 方式)")
    print("=" * 60)
    
    try:
        error_logs = query.query_error_logs(
            start_time=start_time,
            end_time=end_time,
            limit=10
        )
        
        print(f"\n✅ 找到 {len(error_logs)} 条错误日志")
        if error_logs:
            print("\n前3条日志:")
            for i, log in enumerate(error_logs[:3], 1):
                print(f"\n[{i}] {json.dumps(log, ensure_ascii=False, indent=2, default=str)[:200]}...")
                
    except Exception as e:
        print(f"❌ 查询错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
