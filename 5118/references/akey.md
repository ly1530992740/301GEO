# 一键换词 API

> 环境变量: `API_5118_AKEY`
> 介绍页: https://www.5118.com/apistore/detail/54819bb8-4d51-e911-a05e-d4ae52d0f72c

## 基本信息

- **接口地址**: `https://apis.5118.com/wyc/akey`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `txt` | string | ✅ | - | 全文内容，**值必须进行 UrlEncode 编码** |
| `th` | int | ❌ | 3 | 相关词使用次数，越大可读性越强 |
| `filter` | string | ❌ | - | 锁词列表，用"\|"隔开 |
| `corewordfilter` | int | ❌ | 1 | 是否锁住核心词不被替换 |
| `sim` | int | ❌ | 0 | 是否返回相似度 |
| `strict` | int | ❌ | 1 | 严选换词档位，越高越严格 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "corewords": "原创文章|智能工具",
  "like": "0.5824808184143222",
  "data": "换词后的文章内容..."
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `corewords` | 核心词列表 |
| `like` | 相似度 |
| `data` | 换词后内容 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/wyc/akey" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=文章内容&th=3&sim=1&strict=2"
```
