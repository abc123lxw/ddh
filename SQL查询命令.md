# LiteLLM 错误日志 SQL 查询命令

## 📋 数据库访问

```bash
docker exec -e PGPASSWORD=zhipu2025ddh litellm-db-bak psql -U litellm_user -d litellm_db
```

---

## 🔍 三个条件筛选 SQL（推荐）

### 完整查询（时间范围 + 模型 + Key Alias）

```sql
SELECT json_agg(row_to_json(t)) 
FROM (
    SELECT * 
    FROM "LiteLLM_SpendLogs" 
    WHERE 
        -- 1. 时间范围筛选
        "startTime" >= '2025-12-01 00:00:00'::timestamp
        AND "startTime" <= '2025-12-23 23:59:59'::timestamp
        
        -- 2. 模型筛选
        AND "model" = 'external-qwen3-30b'
        
        -- 3. Key Alias 筛选
        AND metadata->>'user_api_key_alias' = 'agent'
        
        -- 4. 只查询错误状态
        AND "status" != 'success'
        AND "status" IS NOT NULL
        
    ORDER BY "startTime" DESC
    LIMIT 100
) t;
```

---

## 📝 单独条件查询

### 1. 只筛选时间范围

```sql
SELECT json_agg(row_to_json(t)) 
FROM (
    SELECT * 
    FROM "LiteLLM_SpendLogs" 
    WHERE 
        "startTime" >= '2025-12-01 00:00:00'::timestamp
        AND "startTime" <= '2025-12-23 23:59:59'::timestamp
        AND "status" != 'success'
        AND "status" IS NOT NULL
    ORDER BY "startTime" DESC
    LIMIT 100
) t;
```

### 2. 只筛选模型

```sql
SELECT json_agg(row_to_json(t)) 
FROM (
    SELECT * 
    FROM "LiteLLM_SpendLogs" 
    WHERE 
        "model" = 'external-qwen3-30b'
        AND "status" != 'success'
        AND "status" IS NOT NULL
    ORDER BY "startTime" DESC
    LIMIT 100
) t;
```

### 3. 只筛选 Key Alias

```sql
SELECT json_agg(row_to_json(t)) 
FROM (
    SELECT * 
    FROM "LiteLLM_SpendLogs" 
    WHERE 
        metadata->>'user_api_key_alias' = 'agent'
        AND "status" != 'success'
        AND "status" IS NOT NULL
    ORDER BY "startTime" DESC
    LIMIT 100
) t;
```

---

## 🚀 命令行执行

```bash
docker exec -e PGPASSWORD=zhipu2025ddh litellm-db-bak psql -U litellm_user -d litellm_db -t -A -c "SELECT json_agg(row_to_json(t)) FROM (SELECT * FROM \"LiteLLM_SpendLogs\" WHERE \"startTime\" >= '2025-12-01 00:00:00'::timestamp AND \"startTime\" <= '2025-12-23 23:59:59'::timestamp AND \"model\" = 'external-qwen3-30b' AND metadata->>'user_api_key_alias' = 'agent' AND \"status\" != 'success' LIMIT 10) t;"
```

---

## ⚠️ 重要提示

1. **Key Alias 查询**：使用 `metadata->>'user_api_key_alias'`（注意是 `->>` 不是 `->`）
2. **时间格式**：使用 `'YYYY-MM-DD HH:MM:SS'::timestamp` 格式
3. **错误状态**：必须添加 `"status" != 'success' AND "status" IS NOT NULL`
4. **表选择**：使用 `LiteLLM_SpendLogs` 表（支持三个条件），`LiteLLM_ErrorLogs` 表不支持 Key Alias 筛选

---

## 📌 快速模板

```sql
SELECT json_agg(row_to_json(t)) 
FROM (
    SELECT * 
    FROM "LiteLLM_SpendLogs" 
    WHERE 
        "startTime" >= '开始时间'::timestamp
        AND "startTime" <= '结束时间'::timestamp
        AND "model" = '模型名'
        AND metadata->>'user_api_key_alias' = 'key_alias'
        AND "status" != 'success'
        AND "status" IS NOT NULL
    ORDER BY "startTime" DESC
    LIMIT 100
) t;
```

**替换参数：**
- `开始时间`：例如 `'2025-12-01 00:00:00'`
- `结束时间`：例如 `'2025-12-23 23:59:59'`
- `模型名`：例如 `'external-qwen3-30b'`
- `key_alias`：例如 `'agent'`
