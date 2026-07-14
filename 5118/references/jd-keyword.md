# 京东长尾词挖掘 API

> 环境变量: `API_5118_JD`
> 介绍页: https://www.5118.com/apistore/detail/4a1a3bfb-dd94-ee11-8da9-e43d1a103140

## 基本信息

- **接口地址**: `https://apis.5118.com/keyword/jd`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | string | ✅ | - | 查询关键词 |
| `page_index` | int | ❌ | 1 | 当前分页 |
| `page_size` | int | ❌ | 100 | 每页数量（最大100） |
| `sort_fields` | int | ❌ | - | 排序字段：1-5118移动流量指数, 2-5118PC流量指数, 3-全网长尾词 |
| `sort_type` | string | ❌ | desc | 排序方式：`asc`/`desc` |

## 返回结构

与淘宝长尾词挖掘API完全一致。返回字段包含：`keyword`, `network_mobile_index`, `network_pc_index`, `long_keyword_count`。

## 调用示例

```bash
curl -X POST "https://apis.5118.com/keyword/jd" \
  -H "Authorization: 你的APIKEY" \
  -d "keyword=手机壳&page_index=1&page_size=10"
```
