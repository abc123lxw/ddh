"""LangGraph分析器 - 使用大模型进行智能分析"""

import logging
import asyncio
from typing import Iterable, Dict, Any, Optional
from datetime import datetime
from openai import AsyncOpenAI
from log_analyzer.plugins.analyzers.base import AbstractAnalyzer

logger = logging.getLogger(__name__)


class LangGraphAnalyzer(AbstractAnalyzer):
    """使用LangGraph进行并发分析"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        mode: str = "sequential",
        concurrency: int = 3,
        chunk_size: int = 5000,
        timeout: int = 60,
        prompts: Optional[Dict[str, str]] = None,
        progress_callback: Optional[callable] = None,
        **kwargs
    ):
        """
        初始化LangGraph分析器
        
        Args:
            base_url: LLM API基础URL
            api_key: API密钥
            model_name: 模型名称
            mode: 分析模式 (sequential/concurrent)
            concurrency: 并发数
            chunk_size: 日志分块大小
            prompts: 自定义提示词
            progress_callback: 进度回调函数 (run_id, total_chunks, processed_chunks)
        """
        super().__init__(**kwargs)
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.mode = mode
        self.concurrency = concurrency
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.prompts = prompts or {}
        self.progress_callback = progress_callback
        self.run_id = None
        
        # 初始化OpenAI客户端
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key
        )
    
    def set_run_id(self, run_id: int):
        """设置run_id用于进度回调"""
        self.run_id = run_id
    
    def analyze(self, data: Any) -> str:
        """分析数据（同步接口）"""
        # 检查是否在事件循环中
        try:
            loop = asyncio.get_running_loop()
            # 如果已经在事件循环中，使用 run_until_complete 会失败
            # 我们需要创建一个新的事件循环在另一个线程中运行
            import concurrent.futures
            import threading
            
            # 创建一个新的事件循环在另一个线程中运行
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
            # 没有运行的事件循环，可以使用 asyncio.run
            return asyncio.run(self._analyze_async(data))
    
    async def _analyze_async(self, data: Any) -> str:
        """异步分析"""
        if isinstance(data, str):
            log_data = data
        elif hasattr(data, '__iter__'):
            log_data = '\n'.join(data)
        else:
            log_data = str(data)
        
        if not log_data.strip():
            return "未发现任何错误日志"
        
        # 分块处理
        chunks = self._chunk_logs(log_data)
        total_chunks = len(chunks)
        logger.info(f"日志分为 {total_chunks} 块进行分析")
        
        # 更新进度：开始分析
        if self.progress_callback and self.run_id:
            self.progress_callback(self.run_id, total_chunks, 0)
        
        # 分析每个块
        if self.mode == "concurrent":
            analyses = await self._analyze_concurrent(chunks)
        else:
            analyses = await self._analyze_sequential(chunks)
        
        # 更新进度：分析完成
        if self.progress_callback and self.run_id:
            self.progress_callback(self.run_id, total_chunks, total_chunks)
        
        # 过滤空结果和无效分析
        valid_analyses = []
        for a in analyses:
            if not a or a.strip() == "<NONE>":
                continue
            # 过滤掉"未发现错误"的分析
            if "未发现任何错误" in a or "未发现错误" in a or "无错误" in a:
                continue
            # 过滤掉过于简短或无效的分析
            if len(a.strip()) < 50:
                continue
            valid_analyses.append(a)
        
        if not valid_analyses:
            return "## 分析结果\n\n✅ **未发现任何错误**\n\n本次分析未检测到任何错误、异常或警告信息。"
        
        # 汇总分析
        summary = await self._summarize(valid_analyses)
        return summary
    
    def _chunk_logs(self, logs: str) -> list:
        """将日志分块"""
        lines = logs.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line.encode('utf-8'))
            if current_size + line_size > self.chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    async def _analyze_sequential(self, chunks: list) -> list:
        """顺序分析"""
        analyses = []
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            logger.info(f"分析块 {i+1}/{total}")
            analysis = await self._analyze_chunk(chunk)
            analyses.append(analysis)
            # 更新进度
            if self.progress_callback and self.run_id:
                self.progress_callback(self.run_id, total, i + 1)
        return analyses
    
    async def _analyze_concurrent(self, chunks: list) -> list:
        """并发分析"""
        semaphore = asyncio.Semaphore(self.concurrency)
        total = len(chunks)
        processed_count = 0
        lock = asyncio.Lock()  # 用于保护processed_count
        
        async def analyze_with_semaphore(chunk, index):
            nonlocal processed_count
            async with semaphore:
                logger.info(f"分析块 {index+1}/{total}")
                result = await self._analyze_chunk(chunk)
                # 更新进度
                async with lock:
                    processed_count += 1
                    if self.progress_callback and self.run_id:
                        logger.info(f"更新进度: {processed_count}/{total} (run_id={self.run_id})")
                        self.progress_callback(self.run_id, total, processed_count)
                return result
        
        tasks = [analyze_with_semaphore(chunk, i) for i, chunk in enumerate(chunks)]
        return await asyncio.gather(*tasks)
    
    async def _analyze_chunk(self, chunk: str) -> str:
        """分析单个日志块"""
        prompt_template = self.prompts.get(
            'analyze_log_chunk',
            """请分析以下错误日志，识别所有错误、异常和警告。
如果未发现错误，请回复 "<NONE>"。
如果发现错误，请详细说明错误类型、严重程度和相关信息。

日志内容：
{log_chunk}
"""
        )
        
        prompt = prompt_template.format(
            log_chunk=chunk,
            current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的日志分析专家，擅长识别和分析系统错误。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=self.timeout  # 使用配置的超时时间
            )
            
            result = response.choices[0].message.content
            return result.strip()
            
        except Exception as e:
            logger.error(f"分析日志块失败: {e}", exc_info=True)
            return f"分析失败: {str(e)}"
    
    async def _summarize(self, analyses: list) -> str:
        """汇总分析结果"""
        if len(analyses) == 1:
            return analyses[0]
        
        prompt_template = self.prompts.get(
            'summarize_analyses',
            """请将以下多个错误分析结果整合为一份完整的分析报告。
报告应包含：错误分类、时间维度分析、应用维度分析、错误关联分析和修复建议。

分析结果：
{analyses}
"""
        )
        
        analyses_text = '\n\n---\n\n'.join(analyses)
        prompt = prompt_template.format(
            analyses=analyses_text,
            current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的运维分析专家，擅长整合多源错误信息并给出修复建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=self.timeout
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"汇总分析失败: {e}", exc_info=True)
            return '\n\n---\n\n'.join(analyses)
