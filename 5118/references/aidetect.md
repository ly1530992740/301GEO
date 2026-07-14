# AI内容检测器 API

> 环境变量: `API_5118_AIDETECT`
> 介绍页: https://www.5118.com/apistore/detail/6b2d78df-3b5c-ee11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/aidetect`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | ✅ | 要检测的内容（100-6000字），**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "linesscore": [
      { "score": 2, "txt": "这是一段疑似由AI生成的文本..." }
    ],
    "percent": "0.85",
    "mintxt": "0"
  }
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data.percent` | AI生成成分比率（0-1） |
| `data.linesscore` | 每段内容评分数组 |
| `data.linesscore[].score` | 分值，<3疑似AI生成 |
| `data.linesscore[].txt` | 对应文本 |
| `data.mintxt` | 0-正常, 1-内容太短无法检测 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/aidetect" \
  -H "Authorization: 你的APIKEY" \
  -d "content=需要检测的文章内容..."
```
