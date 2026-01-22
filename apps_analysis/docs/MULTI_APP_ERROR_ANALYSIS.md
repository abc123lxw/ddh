# 多应用错误日志智能分析

基于大模型的多应用错误日志智能分类、去重、关联分析和修复建议。

## 功能特性

- ✅ **多源数据聚合**: 支持同时分析多个应用的错误日志
- ✅ **智能分类去重**: 大模型理解错误语义，自动分类和去重
- ✅ **错误关联分析**: 分析应用间的错误关联，找出错误传播链和根因
- ✅ **自动修复建议**: 针对根因错误，给出具体的修复建议
- ✅ **时间+应用维度**: 按时间和应用维度分析错误趋势
- ✅ **格式无关**: 大模型可以理解不同格式的日志

## 架构设计

### 应用调用关系

```
dispatcher (8000) → agent-python (8003) → mcp-server (8004)
```

- dispatcher → agent-python: HTTP SSE
- agent-python → mcp-server: MCP 协议

### 数据流

```
多个应用错误日志 → MultiSource → LangGraphAnalyzer → 分析报告 → Database/MinIO
```

## 安装步骤

### 1. 复制 MultiSource 插件

将 `log_analyzer/plugins/sources/multi.py` 复制到 `llm_sentinel-main/log_analyzer/plugins/sources/multi.py`

### 2. 配置任务

在 `llm_sentinel-main/config.yaml` 中添加任务配置（参考配置示例）

### 3. 触发执行

通过 API 触发任务执行

## 使用方法

### 配置示例

```yaml
tasks:
  - name: "Three_Apps_Error_Analysis"
    source:
      name: "multi"
      params:
        sources:
          - type: "docker"
            container_name: "dispatcher"
            hours_ago: 24
            label: "dispatcher"
          - type: "docker"
            container_name: "agent-python"
            hours_ago: 24
            label: "agent-python"
          - type: "docker"
            container_name: "mcp-server"
            hours_ago: 24
            label: "mcp-server"
        call_chain:
          - from: "dispatcher"
            to: "agent-python"
            protocol: "HTTP SSE"
          - from: "agent-python"
            to: "mcp-server"
            protocol: "MCP"
    analyzer:
      name: "langgraph"
      params:
        mode: "sequential"
        prompts:
          analyze_log_chunk: |
            # 错误日志分析任务
            [提示词内容...]
          summarize_analyses: |
            # 多应用错误日志汇总分析
            [提示词内容...]
    sinks:
      - name: "database"
      - name: "file"
      - name: "minio"
```

## 输出内容

报告包含：

1. **整体评估**: 系统健康状况概述
2. **时间维度分析**: 错误趋势、高峰时段
3. **应用维度分析**: 每个应用的错误分类和去重
4. **错误关联分析**: 错误传播链、根因推断
5. **错误根因自动修复建议**: 针对每个根因给出具体修复建议
6. **总结与建议**: 优先级排序、下一步行动
