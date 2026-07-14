# 竞价推广公司挖掘 API

> 环境变量: `API_5118_BIDSITE`
> 介绍页: https://www.5118.com/apistore/detail/d1995837-e3e7-e811-80cd-1866da4dbcc0

## 基本信息

- **接口地址**: `https://apis.5118.com/bidsite`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | string | ✅ | - | 查询关键词 |
| `page_index` | int | ❌ | 1 | 当前分页 |
| `page_size` | int | ❌ | 500 | 每页数量（最大500） |
| `isc` | int | ❌ | 0 | 是否返回高亮HTML标签（0-不返回, 1-返回） |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "total": 350,
    "page_count": 1,
    "keyword_bidsite": [
      {
        "title": "竞价描述标题",
        "intro": "竞价文案",
        "urltitle": "网站标题",
        "url": "example.com",
        "fullurl": "https://www.example.com/landing",
        "companyname": "XX科技有限公司",
        "baidupcweight": 5,
        "bidCount": 120,
        "join_date": "2025-03-01",
        "firstfindtime": "2024-06-15"
      }
    ]
  }
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `title` | 竞价描述标题 |
| `intro` | 竞价文案 |
| `urltitle` | 网站标题 |
| `url` | 网站地址 |
| `fullurl` | 网站完整地址 |
| `companyname` | 企业名称 |
| `baidupcweight` | 5118百度权重 |
| `bidCount` | 竞价发现次数 |
| `join_date` | 最后发现时间 |
| `firstfindtime` | 最早发现时间 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/bidsite" \
  -H "Authorization: 你的APIKEY" \
  -d "keyword=SEO优化&page_index=1&page_size=20"
```
