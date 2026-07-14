# 标题助手 API

> 环境变量: `API_5118_TITLEOPTIMIZER`
> 介绍页: https://www.5118.com/apistore/detail/ce6630c3-07c3-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/ai/titleoptimizer`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keywords` | string | ✅ | 核心关键词或原始标题，**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": "1. 掌握这些技巧，你的标题也能吸引万众瞩目\n2. 标题优化的秘密：如何让点击率翻倍"
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data` | AI优化后的多个候选标题 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/ai/titleoptimizer" \
  -H "Authorization: 你的APIKEY" \
  -d "keywords=SEO优化技巧"
```
