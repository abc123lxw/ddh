-- ============================================
-- 查询 aico_key 密钥在 14 天内使用的模型
-- ============================================

-- 方式 1：查询所有使用的模型（去重，简单列表）
SELECT DISTINCT "model"
FROM "LiteLLM_SpendLogs"
WHERE 
    metadata->>'user_api_key_alias' = 'aico_key'
    AND "startTime" >= NOW() - INTERVAL '14 days'
ORDER BY "model";

-- ============================================

-- 方式 2：按模型统计使用次数（推荐，更详细）
SELECT 
    "model",
    COUNT(*) as "使用次数",
    MIN("startTime") as "首次使用时间",
    MAX("startTime") as "最后使用时间"
FROM "LiteLLM_SpendLogs"
WHERE 
    metadata->>'user_api_key_alias' = 'aico_key'
    AND "startTime" >= NOW() - INTERVAL '14 days'
GROUP BY "model"
ORDER BY "使用次数" DESC;

-- ============================================

-- 方式 3：查询详细记录（包含所有字段）
SELECT json_agg(row_to_json(t)) 
FROM (
    SELECT 
        "model",
        "startTime",
        "status",
        "request_id",
        "end_user",
        "metadata"
    FROM "LiteLLM_SpendLogs" 
    WHERE 
        metadata->>'user_api_key_alias' = 'aico_key'
        AND "startTime" >= NOW() - INTERVAL '14 days'
    ORDER BY "startTime" DESC
    LIMIT 100
) t;

-- ============================================

-- 方式 4：只查询成功的请求（排除错误）
SELECT DISTINCT "model"
FROM "LiteLLM_SpendLogs"
WHERE 
    metadata->>'user_api_key_alias' = 'aico_key'
    AND "startTime" >= NOW() - INTERVAL '14 days'
    AND "status" = 'success'
ORDER BY "model";

-- ============================================

-- 方式 5：只查询错误的请求
SELECT DISTINCT "model"
FROM "LiteLLM_SpendLogs"
WHERE 
    metadata->>'user_api_key_alias' = 'aico_key'
    AND "startTime" >= NOW() - INTERVAL '14 days'
    AND "status" != 'success'
    AND "status" IS NOT NULL
ORDER BY "model";

