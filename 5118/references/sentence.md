# 整句智能原创 API

> 环境变量: `API_5118_SENTENCE`
> 介绍页: https://www.5118.com/apistore/detail/55819bb8-4d51-e911-a05e-d4ae52d0f72c

## 基本信息

- **接口地址**: `https://apis.5118.com/wyc/sentence`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `txt` | string | ✅ | - | 待处理句子（≤150字），**值必须进行 UrlEncode 编码** |
| `strict` | int | ❌ | 0 | 严选换词档位（0-4，越高越严格） |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "text1": "本公司行业从事于...",
    "text2": "本企业专业从事...",
    "text3": "本公司专业从事..."
  }
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data.text1` | 原创建议结果1 |
| `data.text2` | 原创建议结果2 |
| `data.text3` | 原创建议结果3 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/wyc/sentence" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=本公司专业从事网站建设&strict=2"
```
