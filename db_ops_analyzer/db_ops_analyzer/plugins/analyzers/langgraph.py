"""LangGraph分析器 - 使用大模型进行数据库智能分析"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
from openai import AsyncOpenAI
from openai import APIError as OpenAIAPIError
import httpx
from db_ops_analyzer.plugins.analyzers.base import AbstractAnalyzer

logger = logging.getLogger(__name__)


class LangGraphAnalyzer(AbstractAnalyzer):
    """使用大模型进行数据库智能分析"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: int = 60,
        prompts: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        初始化LangGraph分析器
        
        Args:
            base_url: LLM API基础URL
            api_key: API密钥
            model_name: 模型名称
            timeout: 超时时间（秒）
            prompts: 自定义提示词
        """
        super().__init__(**kwargs)
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.prompts = prompts or {}
        self.metadata = {}
        
        # 初始化OpenAI客户端，配置超时
        # httpx.Timeout: connect=连接超时, read=读取超时, write=写入超时, pool=连接池超时
        # 总超时时间 = connect + read，这里设置read为timeout，connect为10秒
        http_timeout = httpx.Timeout(
            connect=10.0,  # 连接超时10秒
            read=float(timeout),  # 读取超时使用配置的timeout
            write=30.0,  # 写入超时30秒
            pool=10.0  # 连接池超时10秒
        )
        
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=http_timeout,
            max_retries=0  # 不自动重试，避免重复超时
        )
    
    def set_metadata(self, metadata: dict):
        """设置报告元数据"""
        self.metadata = metadata or {}
    
    def analyze(self, data: Any) -> str:
        """分析数据（同步接口）"""
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self._analyze_async(data))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        except RuntimeError:
            return asyncio.run(self._analyze_async(data))
    
    async def _analyze_async(self, data: Dict[str, Any]) -> str:
        """异步分析数据库数据"""
        # 准备分析数据（转换为JSON字符串）
        data_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        
        # 获取提示词
        prompt_template = self.prompts.get('analyze_database', self._get_default_prompt())
        prompt = prompt_template.format(
            database_data=data_str,
            current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        try:
            # 调用LLM进行分析
            logger.info(f"开始调用LLM API进行分析（超时设置: {self.timeout}秒）")
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一名资深的数据库运维工程师。报告必须：1)让人一看就对这座数据库有全面了解——实例、数据分布、业务含义、关键配置都要写详细；2)包含具体的配置修改建议（参数名、当前值、建议值、原因），便于照着执行；3)层次清晰：大类用一、二、三、四、五、六，小类用1.2.3.编号。格式：每句独立成行，###标题前后空行，编号列表每项独立成行，仅在1和2之间、3和4之间加空行，---前后空一行。风险须量化等级（Critical/High/Medium/Low）。数据为空时说'无数据'。报告要详尽、可操作。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1600
                ),
                timeout=self.timeout + 5  # 额外5秒缓冲
            )
            
            analysis_result = response.choices[0].message.content.strip()
            logger.info(f"LLM API调用成功，返回结果长度: {len(analysis_result)} 字符")
            
            # 强制格式化报告，确保每个部分之间有明确的空行
            # 注意：只格式化LLM生成的分析部分，不格式化整个报告（因为报告头部包含表格）
            analysis_result = self._force_format_report(analysis_result)
            
            # 格式化报告
            return self._format_report(analysis_result, data)
            
        except asyncio.TimeoutError as e:
            error_msg = f"数据库分析超时（已等待 {self.timeout} 秒）\n\n可能的原因：\n1. LLM API服务响应慢\n2. 数据量过大，分析时间过长\n3. 网络连接不稳定\n\n建议：\n- 检查LLM API服务状态\n- 尝试增加超时时间（当前: {self.timeout}秒）\n- 检查网络连接"
            logger.error(f"数据库分析超时（{self.timeout}秒）: {e}")
            return self._format_error_report(error_msg, data)
        except httpx.TimeoutException as e:
            error_msg = f"LLM API请求超时\n\n错误详情: {str(e)}\n\n可能的原因：\n1. LLM API服务无响应\n2. 网络连接超时\n3. 服务器负载过高\n\n建议：\n- 检查LLM API服务是否正常运行\n- 检查网络连接\n- 尝试增加超时时间（当前: {self.timeout}秒）"
            logger.error(f"LLM API请求超时: {e}")
            return self._format_error_report(error_msg, data)
        except httpx.ConnectError as e:
            error_msg = f"无法连接到LLM API服务\n\n错误详情: {str(e)}\n\n可能的原因：\n1. LLM API服务未运行\n2. base_url配置错误（当前: {self.base_url}）\n3. 网络不通或防火墙阻止\n\n建议：\n- 检查base_url配置是否正确\n- 检查LLM API服务是否运行\n- 测试网络连接: curl {self.base_url}"
            logger.error(f"无法连接到LLM API服务: {e}")
            return self._format_error_report(error_msg, data)
        except OpenAIAPIError as e:
            error_msg = f"LLM API错误\n\n错误详情: {str(e)}\n\n可能的原因：\n1. API密钥无效（当前key: {self.api_key[:10]}...）\n2. 模型名称错误（当前: {self.model_name}）\n3. API服务返回错误\n\n建议：\n- 检查API密钥是否正确\n- 检查模型名称是否正确\n- 查看LLM API服务日志"
            logger.error(f"LLM API错误: {e}")
            return self._format_error_report(error_msg, data)
        except Exception as e:
            error_msg = f"数据库分析失败\n\n错误详情: {str(e)}\n\n错误类型: {type(e).__name__}"
            logger.error(f"数据库分析失败: {e}", exc_info=True)
            return self._format_error_report(error_msg, data)
    
    def _get_default_prompt(self) -> str:
        """获取默认提示词"""
        return """# 数据库运维分析任务

你是一名资深的数据库运维工程师，拥有10年以上的生产环境数据库运维经验。请基于以下数据库信息，提供专业、深入、可操作的运维分析报告。

## 分析数据

```json
{database_data}
```

## 核心要求（必须严格遵守）

1. **优先体现「了解程度」**：
   - 报告的首要目的是让读者对这座数据库、以及库里的数据有清晰认识
   - 先写清楚：对数据库本身的了解（实例概况、对象规模、容量与配置概况）
   - 再写清楚：对库内数据的了解（各库/表大小与占比、数据分布、从库名/表名推断的业务含义、大表/空表等）
   - 最后再写：运维发现、风险与操作建议

2. **配置修改建议**：必须包含具体的配置修改建议，便于读者照着执行。每条建议写清：参数名、当前值、建议值、修改原因、操作方式（如 PostgreSQL 的 ALTER SYSTEM 或改配置文件后重启）。根据当前实例的配置与负载给出，不要泛泛而谈。

3. **格式要求**：
   - 每个句子必须独立成行
   - 不要添加多余的空行（只在1和2之间、3和4之间添加空行）
   - 标题前后必须空行
   - 使用编号列表，每个列表项独立成行，列表项之间不要空行（除了1和2之间、3和4之间）

## 分析重点（顺序不可颠倒）

1. **对数据库的了解程度**（必写、要详细）：
   - 实例概况：数据库类型、版本、监听地址/端口、角色（主/从等）、当前连接数/最大连接数、关键配置项（如 shared_buffers、work_mem、max_connections 等，从 JSON 的 variables 中摘录）
   - 对象概况：有多少个库、多少个 schema、多少张表、多少个索引，并简要说明分布
   - 容量概况：实例总大小、各库大小与占比、最大/最小库、存储趋势（如有）
   - 用两三句话总结：这座库的用途、规模、当前健康度，让人一眼看懂

2. **对库内数据的了解程度**（必写、要详细）：
   - 数据分布：按库列出大小、占比、表数量；如有表级统计，列出各库下的大表 TOP、行数或大小
   - 数据特征：哪些库表多、哪些表特别大或为空、索引数量与分布
   - 业务含义：从库名、表名推断每个库/主要表的业务域（如 ai_dispatcher→AI 调度、user→用户中心、order→订单），让读者知道「库里装的是什么」
   - 数据完整性：哪些库/表有采集到、哪些缺失或异常

3. **运维发现与建议**（在了解程度之后）：
   - 关键发现、容量与性能分析、风险识别、运维操作建议
   - 配置修改建议单独成一大类（六），写具体参数与建议值

4. **层次结构**：报告必须有大类和小类层次。大类用「一、二、三、四、五、六」，小类用「1. 2. 3.」编号列表，让人一眼看出 1 大类下面有 1 2 3 小类。

## 输出格式（必须严格遵守：先写了解程度要详细，再写发现与建议；大类用一/二/三/四/五/六，小类用 1.2.3.）

### 一、数据库了解程度（实例与对象概况，要详细让人一看就懂）

用编号列表写出对这座数据库的整体认识（每条独立成行，列表项之间不要空行，除了1和2之间、3和4之间）。内容要具体、有数字：

1. 实例身份：数据库类型与版本（如 PostgreSQL 15.x）、监听地址与端口（如有）、角色（主/从/单机）
2. 连接与资源：当前连接数/最大连接数（如 5/200）、连接使用率；如有 variables 请摘录关键配置（如 max_connections、shared_buffers、work_mem、effective_cache_size、maintenance_work_mem 等），写出当前值
3. 对象规模：共 X 个库、X 个 schema、X 张表、X 个索引；各库表数量分布（如 XX 库 X 张表、XX 库 X 张表）
4. 容量概况：实例总大小约 X MB；按大小排序列出各库及占比（库名、大小 MB、占比%）；最大库、最小库
5. 综合结论：用两三句话总结这座库的用途、规模、当前健康度（如：以业务库 XX 为主的中小型实例，连接与存储均有余量）

（若某类信息 JSON 中未提供，如实写「未采集到」）

---

### 二、数据了解程度（库内数据概况，要详细让人知道库里装的是什么）

用编号列表写出对库内数据的认识（每条独立成行）。每个库尽量写出用途推断和关键表：

1. 各库数据分布：按大小列出每个用户库的名称、大小（MB）、占比（%）、表数量；如有表级统计，写出各库下最大的几张表及大小/行数
2. 表与索引特征：哪些库表多、哪些表特别大或为空、索引数量分布
3. 业务含义推断：根据库名、表名推断每个库的业务域（如 ai_dispatcher→AI 调度相关、user_db→用户中心、report→报表），让读者一眼知道「这个库是干什么的」
4. 数据完整性：是否所有预期库都有采集、是否有库/表缺失或采集异常

（若某类信息缺失，如实写「未采集到」）

---

### 三、关键发现与容量/性能分析

#### 3.1 关键发现（运维视角）

用编号列表写出关键发现（每条独立成行，列表项之间不要空行，除了1和2之间、3和4之间）。须包含：生产环境风险点（量化等级 Critical/High/Medium/Low）、性能瓶颈、监控盲点、容量问题。

#### 3.2 数据库容量分析

实例总大小、各库容量分布（用编号列表按大小排序写出每个库：库名、大小 MB、占比%、表数量）、存储趋势或风险点。

#### 3.3 性能指标分析

连接池：当前/最大、使用率、来源分布。事务：提交/回滚次数、回滚率、长事务情况。慢查询：条数、TOP 分析或监控盲点说明。缓存命中率、I/O 压力。每项尽量有具体数字和结论。

---

### 四、运维风险识别

用编号列表写出风险（每条独立成行）。须量化风险等级（Critical/High/Medium/Low），并简要说明影响。若无则写「1. 无」。

---

### 五、运维操作建议

用编号列表写出可执行建议（每条独立成行）：立即检查项、持续监控指标与告警阈值、排查步骤与工具、需要启用的监控或扩展。每条写清「做什么、怎么做、预期结果」。

---

### 六、配置修改建议（必须写具体，便于照着执行）

用编号列表写出配置修改建议（每条独立成行）。每条须包含：
- 参数名（如 shared_buffers、max_connections、work_mem）
- 当前值（从 JSON 的 variables 或分析结果中取）
- 建议值及单位（如 256MB、500）
- 修改原因（为何要改、预期效果）
- 操作方式（如 PostgreSQL：ALTER SYSTEM SET 参数=值; 或修改 postgresql.conf 后重启；MySQL：SET GLOBAL 或 my.cnf）

示例格式：
1. shared_buffers：当前 128MB，建议 256MB；原因：提升缓存命中率、减轻 I/O；操作：ALTER SYSTEM SET shared_buffers = '256MB'; 需重启生效。
2. max_connections：当前 200，建议维持或根据业务调整；原因：当前使用率低，暂无压力；操作：如需调整，修改 postgresql.conf 后重启。

若当前配置已较合理、无需修改，也请写出 1～2 条说明（如：当前 shared_buffers 与内存比例合理，无需调整）。

---

**分析时间**: {current_time}
"""
    
    def _force_format_report(self, content: str) -> str:
        """强制格式化报告，确保清晰的层次结构和可读性"""
        import re
        
        # 第一步：保护表格和代码块，避免被后续处理破坏
        placeholders = {}
        placeholder_idx = 0
        
        def create_placeholder(content):
            nonlocal placeholder_idx
            placeholder = f"__PLACEHOLDER_{placeholder_idx}__"
            placeholders[placeholder] = content
            placeholder_idx += 1
            return placeholder
        
        # 保护代码块
        content = re.sub(r'(```[\s\S]*?```)', lambda m: create_placeholder(m.group(0)), content)
        
        # 保护Markdown表格
        content = re.sub(r'(\|.*\|(?:\n\|[:\-\s|]+\|)?(?:\n\|.*\|)+)', lambda m: create_placeholder(m.group(0)), content, flags=re.MULTILINE)
        
        # 第二步：保护标题，避免被后续处理破坏
        title_placeholders = {}
        title_idx = 0
        
        def protect_title(match):
            nonlocal title_idx
            placeholder = f"__TITLE_{title_idx}__"
            title_placeholders[placeholder] = match.group(0)
            title_idx += 1
            return placeholder
        
        # 保护所有标题（包括标题中的句号）
        content = re.sub(r'^(#{1,3}\s+[^\n]+)$', protect_title, content, flags=re.MULTILINE)
        
        # 第三步：在句号、问号、感叹号后添加换行（分割长段落）
        # 但跳过标题占位符和已保护的内容
        lines = content.split('\n')
        processed_lines = []
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # 如果是标题占位符，直接保留
            if line_stripped.startswith('__TITLE_'):
                processed_lines.append(line)
            # 如果是以#开头的标题行，不进行分割
            elif line_stripped.startswith('#'):
                processed_lines.append(line)
            else:
                # 在句号、问号、感叹号后添加换行
                line = re.sub(r'([。！？])([^。！？\n])', r'\1\n\2', line)
                # 英文标点后也添加换行
                line = re.sub(r'([.!?])\s+([A-Za-z\u4e00-\u9fa5])', r'\1\n\n\2', line)
                processed_lines.append(line)
        
        content = '\n'.join(processed_lines)
        
        # 第四步：恢复标题（在添加空行之前）
        for placeholder, title in title_placeholders.items():
            content = content.replace(placeholder, title)
        
        # 检查并修复被错误分割的标题（如 "### 2." 和 "性能分析"）
        lines = content.split('\n')
        fixed_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            line_stripped = line.strip()
            # 如果当前行是标题的一部分（如 "### 2."），检查后续行是否是标题的延续
            if line_stripped.startswith('###') and line_stripped.endswith('.') and i + 1 < len(lines):
                # 跳过空行，查找下一行非空内容
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                
                if j < len(lines):
                    next_line = lines[j].strip()
                    # 如果下一行不是标题，不是列表项，不是表格，可能是标题的延续
                    if (next_line and 
                        not next_line.startswith('#') and 
                        not next_line.startswith('-') and 
                        not next_line.startswith('|') and
                        not next_line.startswith('*') and
                        not re.match(r'^\d+\.\s+', next_line)):
                        # 合并标题（保留原始格式，移除中间的空行）
                        fixed_lines.append(line.rstrip() + ' ' + next_line)
                        i = j + 1
                        continue
            fixed_lines.append(line)
            i += 1
        
        content = '\n'.join(fixed_lines)
        
        # 标题前添加空行（只添加一个）
        content = re.sub(r'([^\n])(\n#{1,3}\s+[^\n]+)', r'\1\n\2', content)
        # 标题后不添加空行（让内容紧跟在标题后）
        
        # 第五步：确保分隔线前后有空行（只添加一个）
        content = re.sub(r'([^\n])(\n---+)', r'\1\n\2', content)
        content = re.sub(r'(---+)(\n[^\n])', r'\1\n\2', content)
        
        # 第六步：处理编号列表，确保每个列表项独立成行
        # 将连续的编号列表项分割（如 "1. xxx 2. yyy" -> "1. xxx\n2. yyy"）
        content = re.sub(r'(\d+\.\s+[^\n\d]+?)(\s+)(\d+\.\s+)', r'\1\n\3', content)
        
        # 第七步：只在特定编号之间添加空行（1和2之间、3和4之间）
        # 1和2之间添加空行
        content = re.sub(r'(1\.\s+[^\n]+)(\n)(2\.\s+)', r'\1\n\n\3', content)
        # 3和4之间添加空行
        content = re.sub(r'(3\.\s+[^\n]+)(\n)(4\.\s+)', r'\1\n\n\3', content)
        
        # 第八步：恢复被保护的内容
        for placeholder, original_content in placeholders.items():
            content = content.replace(placeholder, original_content)
        
        # 第九步：按行处理，最小化空行（只在1和2之间、3和4之间、标题前、分隔线前后保留）
        lines = content.split('\n')
        formatted_lines = []
        prev_line = None
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # 如果是空行，跳过（后面会按需添加）
            if not line_stripped:
                continue
            
            # 检查是否是标题
            is_title = line_stripped.startswith('#')
            # 检查是否是分隔线
            is_hr = line_stripped.startswith('---')
            # 检查是否是编号列表项
            list_match = re.match(r'^(\d+)\.\s+', line_stripped)
            is_list_item = bool(list_match)
            list_num = int(list_match.group(1)) if list_match else 0
            
            # 检查前一行
            prev_stripped = prev_line.strip() if prev_line else ''
            prev_list_match = re.match(r'^(\d+)\.\s+', prev_stripped) if prev_stripped else None
            prev_list_num = int(prev_list_match.group(1)) if prev_list_match else 0
            
            # 标题前添加空行
            if is_title and prev_line and not prev_line.strip().startswith('#'):
                formatted_lines.append('')
            
            # 分隔线前添加空行
            if is_hr and prev_line and not prev_line.strip().startswith('---'):
                formatted_lines.append('')
            
            # 1和2之间添加空行
            if list_num == 2 and prev_list_num == 1:
                formatted_lines.append('')
            
            # 3和4之间添加空行
            if list_num == 4 and prev_list_num == 3:
                formatted_lines.append('')
            
            # 添加当前行
            formatted_lines.append(line)
            
            # 分隔线后添加空行
            if is_hr and i + 1 < len(lines) and lines[i + 1].strip():
                formatted_lines.append('')
            
            prev_line = line
        
        # 将处理后的行合并为字符串
        result = '\n'.join(formatted_lines)
        
        # 最后清理：确保1和2之间、3和4之间有且仅有一个空行
        # 1和2之间
        result = re.sub(r'(1\.\s+[^\n]+)(\n+)(2\.\s+)', r'\1\n\n\3', result)
        # 3和4之间
        result = re.sub(r'(3\.\s+[^\n]+)(\n+)(4\.\s+)', r'\1\n\n\3', result)
        
        # 最终清理：移除所有多余的空行（连续2个以上空行变成1个，但保留1和2、3和4之间的空行）
        # 先保护1和2、3和4之间的空行
        result = re.sub(r'(1\.\s+[^\n]+)\n\n(2\.\s+)', r'\1__SPACE_1_2__\2', result)
        result = re.sub(r'(3\.\s+[^\n]+)\n\n(4\.\s+)', r'\1__SPACE_3_4__\2', result)
        # 移除其他多余空行
        result = re.sub(r'\n{2,}', '\n', result)
        # 恢复保护的空行
        result = result.replace('__SPACE_1_2__', '\n\n')
        result = result.replace('__SPACE_3_4__', '\n\n')
        
        return result.strip()
    
    def _format_report(self, analysis_result: str, data: Dict[str, Any]) -> str:
        """格式化报告"""
        database_type = data.get('database_type', 'Unknown')
        host = data.get('host', 'Unknown')
        database = data.get('database', 'Unknown')
        report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取数据库列表，计算大小和占比
        databases = data.get('databases', [])
        databases_info = ""
        if databases:
            # 过滤系统数据库
            user_databases = [db for db in databases if db.get('database_name') not in ['template0', 'template1']]
            db_count = len(user_databases)
            databases_info = f"\n> **实例数据库数量**: {db_count} 个"
            
            if db_count > 0:
                # 计算总大小
                total_size = 0
                db_sizes = {}
                for db in user_databases:
                    db_name = db.get('database_name', '')
                    # PostgreSQL使用database_size字段（字节）
                    db_size = db.get('database_size', 0)
                    if isinstance(db_size, (int, float)) and db_size > 0:
                        db_sizes[db_name] = db_size
                        total_size += db_size
                
                # 生成数据库列表，包含大小和占比
                if total_size > 0 and db_sizes:
                    db_list_items = []
                    for db in sorted(user_databases, key=lambda x: db_sizes.get(x.get('database_name', ''), 0), reverse=True)[:10]:
                        db_name = db.get('database_name', '')
                        db_size = db_sizes.get(db_name, 0)
                        if db_size > 0:
                            # 转换为MB
                            size_mb = db_size / (1024 * 1024)
                            percentage = (db_size / total_size) * 100
                            db_list_items.append(f"{db_name} ({size_mb:.1f}MB, {percentage:.1f}%)")
                        else:
                            db_list_items.append(db_name)
                    
                    databases_info += f"\n> **数据库列表（按大小排序）**: {', '.join(db_list_items)}"
                    if len(user_databases) > 10:
                        databases_info += f" 等（共{len(user_databases)}个）"
                else:
                    # 如果没有大小信息，只显示名称
                    db_names = [db.get('database_name', '') for db in user_databases[:10]]
                    databases_info += f"\n> **数据库列表**: {', '.join(db_names)}"
                    if len(user_databases) > 10:
                        databases_info += f" 等（共{len(user_databases)}个）"
        
        header = f"""# 📊 数据库运维分析报告

> **报告生成时间**: {report_time}  
> **数据库类型**: {database_type}  
> **数据库地址**: {host}  
> **分析数据库**: {database}{databases_info}

---

"""
        
        # 添加数据统计（纯 Markdown 表格，便于正确渲染且可视性好）
        errors = data.get('errors', [])
        tables = data.get('tables', [])
        tables_by_db = {}
        for t in tables:
            db_name = t.get('database_name', database)
            if db_name not in tables_by_db:
                tables_by_db[db_name] = []
            tables_by_db[db_name].append(t)

        slow_n = len(data.get('slow_queries', []))
        conn_n = len(data.get('processlist', []))
        status_n = len(data.get('status', {}))
        vars_n = len(data.get('variables', {}))
        idx_n = len(data.get('indexes', []))
        tbl_n = len(tables)

        def _status(ok: bool, empty_msg: str = "无数据") -> str:
            return "正常" if ok else empty_msg

        # 表分布、数据收集问题用 Markdown 列表
        extra_lines = []
        if tables_by_db:
            extra_lines.append("\n**表分布**\n")
            for db_name, db_tables in sorted(tables_by_db.items()):
                extra_lines.append(f"- **{db_name}**: {len(db_tables)} 个表\n")
        if errors:
            extra_lines.append("\n**⚠️ 数据收集问题**\n")
            for err in errors[:5]:
                extra_lines.append(f"- {err}\n")
        extra_block = "".join(extra_lines)

        stats_section = f"""## 📈 数据统计

| 数据类型 | 数量 | 状态 |
| :--- | ---: | :--- |
| 慢查询 | {slow_n} | {_status(slow_n > 0)} |
| 活跃连接 | {conn_n} | {_status(conn_n > 0)} |
| 状态变量 | {status_n} | {_status(status_n > 0)} |
| 配置变量 | {vars_n} | {_status(vars_n > 0, "未收集或为空")} |
| 索引 | {idx_n} | {_status(idx_n > 0)} |
| 表 | {tbl_n} | {_status(tbl_n > 0)} |
{extra_block}
---

"""
        
        # 确保analysis_result前面有空行
        if analysis_result and not analysis_result.startswith('\n'):
            analysis_result = '\n' + analysis_result
        
        return header + stats_section + analysis_result
    
    def _format_error_report(self, error_msg: str, data: Dict[str, Any]) -> str:
        """格式化错误报告"""
        database_type = data.get('database_type', 'Unknown')
        host = data.get('host', 'Unknown')
        report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return f"""# 📊 数据库运维分析报告

> **报告生成时间**: {report_time}  
> **数据库类型**: {database_type}  
> **数据库地址**: {host}  
> **状态**: ❌ 分析失败

---

## ⚠️ 错误信息

{error_msg}

## 📋 收集的数据概览

- **慢查询数量**: {len(data.get('slow_queries', []))}
- **活跃连接数**: {len(data.get('processlist', []))}
- **表数量**: {len(data.get('tables', []))}

---

**注意**: 由于分析过程出错，无法生成完整的分析报告。请检查数据收集是否正常。
"""
