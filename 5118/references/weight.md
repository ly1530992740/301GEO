# 网站5118权重查询 API

> 环境变量: `API_5118_WEIGHT`
> 介绍页: https://www.5118.com/apistore/detail/69429f16-24f0-e711-80c8-1866da4dbcc0

## 基本信息

- **接口地址**: `https://apis.5118.com/weight`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 要查询的网站域名 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "result": [
      { "BaiduPCWeight": "5" },
      { "BaiduMobileWeight": "6" },
      { "SMWeight": "3" },
      { "TouTiaoWeight": "4" }
    ]
  }
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `BaiduPCWeight` | 百度PC权重 |
| `BaiduMobileWeight` | 百度移动权重 |
| `SMWeight` | 神马权重 |
| `TouTiaoWeight` | 头条权重 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/weight" \
  -H "Authorization: 你的APIKEY" \
  -d "url=www.example.com"
```
