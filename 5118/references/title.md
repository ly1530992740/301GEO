# 智能标题生成 API

> 环境变量: `API_5118_TITLE`
> 介绍页: https://www.5118.com/apistore/detail/d189427f-310c-ea11-8da1-20040ff9d71d

## 基本信息

- **接口地址**: `https://apis.5118.com/wyc/title`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `txt` | string | ✅ | 需要生成标题的文本（≤5000字符），**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": "5118对伪原创降权网站进行检测,一键生成智能原创文章..."
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data` | 生成的智能标题 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/wyc/title" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=文章正文内容"
```
