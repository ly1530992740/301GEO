# PC-网站排名词导出 API v2

> 环境变量: `API_5118_BAIDUPC_V2`
> 介绍页: https://www.5118.com/apistore/detail/8df3d6ed-2b12-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/keyword/pc/v2`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 要查询的网站域名或URL |
| `page_index` | int | ❌ | 1 | 当前页码 |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "total": 590511,
    "page_count": 1182,
    "page_index": 1,
    "page_size": 500,
    "baidupc": [
      {
        "keyword": "关键词",
        "rank": 1,
        "page_title": "网页标题",
        "url": "https://www.example.com/page",
        "bidword_companycount": 5,
        "long_keyword_count": 500,
        "index": 1063,
        "mobile_index": 919,
        "haosou_index": 1163,
        "douyin_index": 89,
        "toutiao_index": 256,
        "bidword_kwc": 1,
        "bidword_pcpv": 240,
        "bidword_wisepv": 1433,
        "sem_reason": "",
        "sem_price": "0.35~4.57",
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
| `keyword` | 关键词名称 |
| `rank` | 当前排名 |
| `page_title` | 对应网页标题 |
| `url` | 对应网页URL |
| `bidword_companycount` | 竞价该词的公司数量 |
| `long_keyword_count` | 长尾词数量 |
| `index` | 流量指数（百度PC指数） |
| `mobile_index` | 百度移动指数 |
| `haosou_index` | 360指数 |
| `douyin_index` | 抖音指数 |
| `toutiao_index` | 头条指数 |
| `bidword_kwc` | 竞价竞争度（1-高, 2-中, 3-低） |
| `bidword_pcpv` | PC端日检索量 |
| `bidword_wisepv` | 移动端日检索量 |
| `sem_reason` | 流量特点 |
| `sem_price` | SEM点击价格参考 |
| `bidword_recommend_price_avg` | 竞价点击平均价格 |
| `google_index` | 谷歌指数 |
| `kuaishou_index` | 快手指数 |
| `weibo_index` | 微博指数 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/keyword/pc/v2" \
  -H "Authorization: 你的APIKEY" \
  -d "url=www.example.com&page_index=1"
```
