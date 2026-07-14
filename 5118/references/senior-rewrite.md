# 一键改写升级版 API

> 环境变量: `API_5118_SENIOR_REWRITE`
> 介绍页: https://www.5118.com/apistore/detail/b07bc4a8-b9eb-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/wyc/seniorrewrite`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `txt` | string | ✅ | - | 全文内容（<5000字符），**值必须进行 UrlEncode 编码** |
| `keephtml` | string | ❌ | true | 是否保留HTML格式 |
| `sim` | int | ❌ | 0 | 是否返回相似度 |

## 返回字段

| 字段 | 说明 |
|------|------|
| `like` | 相似度 |
| `data` | 改写后的内容 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/wyc/seniorrewrite" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=原始文章内容&sim=1"
```
