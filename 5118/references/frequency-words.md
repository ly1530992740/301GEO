# 细分行业分析 API

> 环境变量: `API_5118_FREQ_WORDS`
> 介绍页: https://www.5118.com/apistore/detail/19bb1381-bcbc-ec11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/tradeseg`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keyword` | string | ✅ | 要查询的关键词 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": [
    {
      "Word": "做法",
      "Frequency": 46826,
      "Rate": 5.58
    },
    {
      "Word": "广东",
      "Frequency": 49006,
      "Rate": 5.84
    }
  ]
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `Word` | 高频词 |
| `Frequency` | 出现频次 |
| `Rate` | 占比（百分比数值） |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/tradeseg" \
  -H "Authorization: 你的APIKEY" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "keyword=美食"
```
