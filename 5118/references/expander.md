# 文本扩写精灵 API

> 环境变量: `API_5118_EXPANDER`
> 介绍页: https://www.5118.com/apistore/detail/a3340d06-13b8-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/ai/autoexpander`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keywords` | string | ✅ | - | 文本或搜索关键词（5字以上300字以内），**值必须进行 UrlEncode 编码** |
| `wish_content_count` | int | ❌ | 500 | 扩写期望字数（最大1000） |
| `modelversion` | string | ❌ | 1.0 | 模型版本：1.0/2.0/3.0 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": "金色童年时光，这种光芒熠熠的时光，每个人都曾经经历过..."
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data` | 扩写后的结果文本 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/ai/autoexpander" \
  -H "Authorization: 你的APIKEY" \
  -d "keywords=金色童年时光&wish_content_count=500&modelversion=2.0"
```
