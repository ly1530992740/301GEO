# 段落组合大师 API

> 环境变量: `API_5118_ARTICLEWRITER`
> 介绍页: https://www.5118.com/apistore/detail/604fee0d-845d-ec11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/articlewriter`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keywords` | string | ✅ | - | 关键词（最多5个，用空格隔开），**值必须进行 UrlEncode 编码** |
| `exclude_keywords` | string | ✅ | - | 需要过滤的词，**值必须进行 UrlEncode 编码** |
| `max_content_count` | int | ✅ | - | 返回文章段落总字数限制（≤3000） |
| `startTime` | string | ✅ | - | 起始日期，格式 `yyyy-MM-dd` |
| `endTime` | string | ✅ | - | 结束日期，格式 `yyyy-MM-dd` |
| `scheme` | int | ❌ | 1 | 1-优选, 2-多样化 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "keywords": "SEO 运营",
  "rowcount": 5,
  "total": 1500,
  "content": "在当今的数字化时代，SEO运营已成为企业获取流量的核心手段..."
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `keywords` | 使用的关键词 |
| `rowcount` | 文章段落行数 |
| `total` | 返回内容总字数 |
| `content` | 组合生成的文章段落正文 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/articlewriter" \
  -H "Authorization: 你的APIKEY" \
  -d "keywords=SEO 运营&exclude_keywords=广告&max_content_count=1500&startTime=2025-01-01&endTime=2025-03-17&scheme=1"
```
