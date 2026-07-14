# 原创度检测 API

> 环境变量: `API_5118_ORIGINAL`
> 介绍页: https://www.5118.com/apistore/detail/621edaa6-0c32-ea11-8da2-20040ff9d71d

## 基本信息

- **接口地址**: `https://apis.5118.com/wyc/original`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `txt` | string | ✅ | 需要检查的文本（<7500字符），**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": [
    {
      "content": "同质化内容片段",
      "originalvalue": "serious",
      "platform": "百度",
      "sort": 15,
      "paragraphposition": 2
    }
  ]
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `content` | 同质化程度内容 |
| `originalvalue` | 同质化程度：`serious`(严重), `secondary`(中等), `low`(轻微) |
| `platform` | 平台 |
| `sort` | 起始位置 |
| `paragraphposition` | 所在段落数 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/wyc/original" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=需要检查原创度的文章内容"
```
