# GEO 一键分析配置手册

更新时间：2026-07-10

本文说明 `.env` 中会影响 API 调用次数、运行成本和运行速度的配置项。

## 1. 多 AI 推荐成本配置

这些配置会直接影响 Qwen、豆包、元宝、DeepSeek 的调用次数。

```env
# 每次生成几个真实用户问题。默认 5。
# 公式：推荐阶段调用次数 = GEO_AI_PROMPT_COUNT x AI平台数量
# 当前 AI 平台通常是 Qwen、豆包、元宝、DeepSeek，即 5 x 4 = 20 次调用。
GEO_AI_PROMPT_COUNT=5

# 品牌诊断问题数量。允许出现客户品牌，用于口碑、风险、情绪分分析，不参与主推荐排名。
# 每增加 1 个问题，会让 Qwen、豆包、元宝、DeepSeek 各多调用 1 次。设为 0 可关闭。
GEO_AI_BRAND_DIAGNOSTIC_PROMPT_COUNT=3

# 竞品直接对比问题数量。先用中立推荐得出竞品，再拿客户品牌和头部竞品直接对比。
# 不参与主推荐排名。每增加 1 个问题，会让 Qwen、豆包、元宝、DeepSeek 各多调用 1 次。
GEO_AI_COMPARISON_PROMPT_COUNT=2

# 每个问题让 AI 最多推荐几个品牌。默认 10。
# 数字越大，返回内容越长，解析和后续统计越复杂。
GEO_AI_RECOMMENDATIONS_PER_PROMPT=10

# 是否调用 Qwen 生成 Prompt 组。
# true：多一次 Qwen 调用，但问题更贴近业务。
# false：不额外调用 Qwen，使用程序规则生成兜底问题。
GEO_AI_ENABLE_PROMPT_DISCOVERY=true
```

建议：

1. 日常测试用 `GEO_AI_PROMPT_COUNT=2` 或 `3`。
2. 给客户正式跑报告用 `GEO_AI_PROMPT_COUNT=5`。
3. 想更接近 Topify 的监控密度，可以后期提高到 `10`，但成本约翻倍。

## 2. 五平台声量估算配置

当前五平台声量仍然是 AI 估算，不是百度、搜狗、360、抖音、小红书官方真实接口统计。

```env
# 进入五平台声量估算的品牌数。默认 10。
# 包含 AI 推荐前 10 个品牌，并确保客户品牌也在内。
GEO_AI_VISIBILITY_BRAND_LIMIT=10
```

建议：

1. 正式报告保持 `10`。
2. 调试时可降到 `5`，速度更快。
3. 后续如果接入真实搜索/平台 API，这个字段仍可作为统计品牌数量上限。

## 3. 引用链接和文章抓取配置

这些配置主要影响运行时间、抓取失败数量和后续内容分析质量。

```env
# 最多保留多少个 AI 返回的引用链接/搜索链接。
GEO_AI_SOURCE_LINK_LIMIT=80

# 最多抓取多少个文章链接正文。
# 数字越大越慢，也越容易遇到反爬、TLS、连接重置、502 等失败。
GEO_AI_ARTICLE_FETCH_LIMIT=40
```

建议：

1. 日常测试用 `GEO_AI_ARTICLE_FETCH_LIMIT=10`。
2. 正式客户报告用 `40`。
3. 不建议第一版超过 `80`，否则失败链接会明显变多，客户观感反而变差。

## 4. API Key 与模型配置

### Qwen

```env
DASHSCOPE_API_KEY=你的QwenKey
QWEN_SEARCH_MODEL=qwen-plus
QWEN_ANALYSIS_MODEL=qwen3.7-max
QWEN_WRITING_MODEL=qwen-plus
```

Qwen 当前用途：

1. 生成产品画像。
2. 生成 Prompt 组。
3. 参与多 AI 推荐排名。
4. 文章与品牌定位分析。

### 豆包

```env
DOUBAO_API_KEY=你的豆包Key
DOUBAO_RESPONSES_API_URL=https://ark.cn-beijing.volces.com/api/v3/responses
DOUBAO_MODEL=doubao-seed-evolving
DOUBAO_TIMEOUT_SECONDS=90
```

豆包当前用途：

1. 参与多 AI 推荐排名。
2. 参与五平台声量估算。

### 元宝

```env
YUANBAO_API_KEY=你的元宝Key
YUANBAO_RESPONSES_API_URL=https://tokenhub.tencentmaas.com/v1/responses
YUANBAO_MODEL=hy3
YUANBAO_TIMEOUT_SECONDS=30
```

元宝当前用途：

1. 参与多 AI 推荐排名。
2. 参与五平台声量估算。

### DeepSeek

```env
DEEPSEEK_API_KEY=你的DeepSeekKey
DEEPSEEK_CHAT_API_URL=https://api.deepseek.com/chat/completions
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=30
```

DeepSeek 当前用途：

1. 参与多 AI 推荐排名。
2. 参与五平台声量估算。

## 5. 一次正式报告的大致调用次数

默认配置：

```env
GEO_AI_PROMPT_COUNT=5
GEO_AI_RECOMMENDATIONS_PER_PROMPT=10
GEO_AI_VISIBILITY_BRAND_LIMIT=10
GEO_AI_ENABLE_PROMPT_DISCOVERY=true
```

预计调用：

| 阶段 | 调用数量 |
|---|---:|
| 产品画像 Qwen | 1 |
| Prompt 组生成 Qwen | 1 |
| 多 AI 推荐排名 | 5 个问题 x 4 个平台 = 20 |
| 五平台声量估算 | 4 |
| 文章与定位分析 Qwen | 1 |
| 合计 | 约 27 次 AI 调用 |

说明：

1. 如果某个平台缺 API Key，该平台会失败并记录状态，不会中断全部流程。
2. 文章网页抓取不是 AI 调用，但会消耗时间，也可能被目标网站反爬。
3. 媒介库同步和报价查询会调用媒介库接口。

## 6. 推荐配置

### 开发调试

```env
GEO_AI_PROMPT_COUNT=2
GEO_AI_RECOMMENDATIONS_PER_PROMPT=5
GEO_AI_VISIBILITY_BRAND_LIMIT=5
GEO_AI_SOURCE_LINK_LIMIT=20
GEO_AI_ARTICLE_FETCH_LIMIT=10
GEO_AI_ENABLE_PROMPT_DISCOVERY=false
```

### 客户正式报告

```env
GEO_AI_PROMPT_COUNT=5
GEO_AI_RECOMMENDATIONS_PER_PROMPT=10
GEO_AI_VISIBILITY_BRAND_LIMIT=10
GEO_AI_SOURCE_LINK_LIMIT=80
GEO_AI_ARTICLE_FETCH_LIMIT=40
GEO_AI_ENABLE_PROMPT_DISCOVERY=true
```

### 高密度监控

```env
GEO_AI_PROMPT_COUNT=10
GEO_AI_RECOMMENDATIONS_PER_PROMPT=10
GEO_AI_VISIBILITY_BRAND_LIMIT=15
GEO_AI_SOURCE_LINK_LIMIT=120
GEO_AI_ARTICLE_FETCH_LIMIT=60
GEO_AI_ENABLE_PROMPT_DISCOVERY=true
```

高密度监控适合后期自动化，不建议当前日常测试使用。
