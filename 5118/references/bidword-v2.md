# 网站竞价词挖掘 API v2

> 环境变量: `API_5118_BIDWORD_V2`
> 介绍页: https://www.5118.com/apistore/detail/8af3d6ed-2b12-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/bidword/v2`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 查询域名 |
| `page_index` | int | ❌ | 1 | 当前分页 |
| `page_size` | int | ❌ | 500 | 每页数量（最大500） |
| `isc` | int | ❌ | 0 | 是否返回高亮HTML标签（0-不返回, 1-返回） |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "total": 1200,
    "page_count": 3,
    "keywords": [
      {
        "keyword": "SEO优化",
        "title": "竞价标题",
        "intro": "竞价文案",
        "bidword_semprice": "5.60",
        "bidword_pcpv": 384,
        "bidword_wisepv": 115,
        "bidword_kwc": 1,
        "index": 330,
        "mobile_index": 212,
        "urlcount_30day": 15,
        "urlcount": 45,
        "firstfindtime": "2024-01-15",
        "joindate": "2025-03-01",
        "bidword_recommend_price_avg": "4.65",
        "google_index": 1200,
        "kuaishou_index": 35,
        "weibo_index": 78
      }
    ]
  }
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `keyword` | 竞价关键词 |
| `title` | 竞价标题 |
| `intro` | 竞价文案 |
| `bidword_semprice` | 竞价点击价格 |
| `bidword_pcpv` | PC日检索量 |
| `bidword_wisepv` | 移动日检索量 |
| `bidword_kwc` | 竞价竞争度（1-高, 2-中, 3-低） |
| `index` | 流量指数 |
| `mobile_index` | 移动指数 |
| `urlcount_30day` | 最近30天竞价公司数 |
| `urlcount` | 总竞价公司数 |
| `firstfindtime` | 最早发现时间 |
| `joindate` | 最后发现时间 |
| `bidword_recommend_price_avg` | 竞价点击平均价格 |
| `google_index` | 谷歌指数 |
| `kuaishou_index` | 快手指数 |
| `weibo_index` | 微博指数 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/bidword/v2" \
  -H "Authorization: 你的APIKEY" \
  -d "url=www.example.com&page_index=1&page_size=20"
```
