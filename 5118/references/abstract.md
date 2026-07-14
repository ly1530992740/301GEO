# 智能摘要提取 API

> 环境变量: `API_5118_ABSTRACT`
> 介绍页: https://www.5118.com/apistore/detail/c4d0d2ba-7bd0-e911-80d9-1866da4dbcc0

## 基本信息

- **接口地址**: `https://apis.5118.com/abstract`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `txt` | string | ✅ | 需要提取摘要的文本，**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "Desc": "本文介绍了肠粉的制作过程及其背后的细节..."
  }
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data.Desc` | 提取出的文章摘要 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/abstract" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=文章正文内容"
```
