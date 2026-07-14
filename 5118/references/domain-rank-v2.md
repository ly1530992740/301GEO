# PC-整网站排名词导出 API v2

> 环境变量: `API_5118_DOMAIN_V2`
> 介绍页: https://www.5118.com/apistore/detail/8ff3d6ed-2b12-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/keyword/domain/v2`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 要查询的网站域名 |
| `page_index` | int | ❌ | 1 | 当前分页 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "total": 12345,
    "page_count": 25,
    "page_index": 1,
    "page_size": 500,
    "domain": [
      {
        "keyword": "关键词",
        "rank": 1,
        "index": 1063,
        "mobile_index": 919,
        "haosou_index": 1163,
        "page_title": "网页标题",
        "url": "https://www.example.com/page",
        "bidword_companycount": 5,
        "bidword_kwc": 1,
        "bidword_pcpv": 240,
        "bidword_wisepv": 1433,
        "bidword_recommend_price_avg": "3.25",
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
| `rank` | 排名 |
| `index` | 流量指数（百度PC指数） |
| `mobile_index` | 百度移动指数 |
| `haosou_index` | 360指数 |
| `page_title` | 标题 |
| `url` | 网址 |
| `bidword_companycount` | 竞价公司数 |
| `bidword_kwc` | 竞价竞争度（1-高, 2-中, 3-低） |
| `bidword_pcpv` | PC检索量 |
| `bidword_wisepv` | 移动检索量 |
| `bidword_recommend_price_avg` | 竞价点击平均价格 |
| `google_index` | 谷歌指数 |
| `kuaishou_index` | 快手指数 |
| `weibo_index` | 微博指数 |

分页信息：`total`, `page_count`, `page_index`, `page_size`

## 调用示例

```bash
curl -X POST "https://apis.5118.com/keyword/domain/v2" \
  -H "Authorization: 你的APIKEY" \
  -d "url=example.com&page_index=1"
```
