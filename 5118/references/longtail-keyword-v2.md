# 海量长尾词挖掘 API v2

> 环境变量: `API_5118_LONGTAIL_V2`
> 介绍页: https://www.5118.com/apistore/detail/8cf3d6ed-2b12-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/keyword/word/v2`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded; charset=utf-8`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | string | ✅ | - | 要查询的关键词 |
| `page_index` | int | ❌ | 1 | 当前分页页码 |
| `page_size` | int | ❌ | 100 | 每页数据量（最大100） |
| `sort_fields` | int | ❌ | 4 | 排序字段：2-竞价公司数, 3-长尾词数, 4-流量指数, 5-百度移动指数, 6-360指数, 7-PC日检索量, 8-移动日检索量, 9-竞争剧烈度 |
| `sort_type` | string | ❌ | desc | 排序方式：`asc`(升序) / `desc`(降序) |
| `filter` | int | ❌ | 1 | 快速过滤：1-所有词, 2-流量词, 3-流量指数词, 4-移动指数词, 5-360指数词, 6-流量特点词, 7-PC日检索量词, 8-移动日检索量词, 9-有竞价的词 |
| `filter_date` | string | ❌ | - | 筛选日期，格式 `yyyy-MM-dd` |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "total": 52,
    "page_count": 18,
    "page_index": 1,
    "page_size": 3,
    "word": [
      {
        "keyword": "衬衫",
        "index": 1063,
        "mobile_index": 919,
        "haosou_index": 1163,
        "douyin_index": 89,
        "toutiao_index": 256,
        "long_keyword_count": 6045520,
        "bidword_company_count": 185,
        "page_url": "",
        "bidword_kwc": 1,
        "bidword_pcpv": 240,
        "bidword_wisepv": 1433,
        "sem_reason": "",
        "sem_price": "0.35~4.57",
        "sem_recommend_price_avg": "3.25",
        "google_index": 12100,
        "kuaishou_index": 580,
        "weibo_index": 320
      }
    ]
  }
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `keyword` | 关键词 |
| `index` | 流量指数（百度PC指数） |
| `mobile_index` | 百度移动指数 |
| `haosou_index` | 360指数 |
| `douyin_index` | 抖音指数 |
| `toutiao_index` | 头条指数 |
| `long_keyword_count` | 相关长尾词数量 |
| `bidword_company_count` | 竞价公司数量 |
| `page_url` | 推荐网站 |
| `bidword_kwc` | 竞价竞争度（1-高, 2-中, 3-低） |
| `bidword_pcpv` | PC端日检索量 |
| `bidword_wisepv` | 移动端日检索量 |
| `sem_reason` | 流量特点 |
| `sem_price` | SEM 点击价格参考 |
| `sem_recommend_price_avg` | SEM 推荐出价均价 |
| `google_index` | 谷歌指数 |
| `kuaishou_index` | 快手指数 |
| `weibo_index` | 微博指数 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/keyword/word/v2" \
  -H "Authorization: 你的APIKEY" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "keyword=SEO优化&page_index=1&page_size=10"
```
