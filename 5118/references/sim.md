# 相似度检测 API

> 环境变量: `API_5118_SIM`
> 介绍页: https://www.5118.com/apistore/detail/53819bb8-4d51-e911-a05e-d4ae52d0f72c

## 基本信息

- **接口地址**: `https://apis.5118.com/wyc/sim`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `orgtxt` | string | ✅ | 原文本，**值必须进行 UrlEncode 编码** |
| `newtxt` | string | ✅ | 新文本（对比文本），**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "like": "0.558412017167382"
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `like` | 两个文本的相似度分值（0-1） |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/wyc/sim" \
  -H "Authorization: 你的APIKEY" \
  -d "orgtxt=原始文本内容&newtxt=修改后的文本内容"
```
