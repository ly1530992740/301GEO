# 百家号排名词导出 API

> 环境变量: `API_5118_BAIJIAHAO`
> 介绍页: https://www.5118.com/apistore/detail/96e89478-6d48-ee11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/keyword/baijiahao`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keyword` | string | ✅ | 要查询的百家号名称 |
| `platform` | string | ✅ | 查询平台：`pc` 或 `mobile` |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": [
    {
      "keyword": "关键词",
      "rank": 1,
      "page_title": "页面标题",
      "page_url": "https://baijiahao.baidu.com/xxx",
      "bidword_company_count": 5,
      "long_keyword_count": 300,
      "index": 1063,
      "mobile_index": 919,
      "haosou_index": 1163,
      "bidword_pcpv": 240,
      "bidword_recommendprice_avg": "3.25",
      "bidword_wisepv": 1433,
      "toutiao_index": 256,
      "douyin_index": 89,
      "kuai_shou_index": 580,
      "google_index": 12100,
      "weibo_index": 320
    }
  ]
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `keyword` | 关键词 |
| `rank` | 排名 |
| `page_title` | 页面标题 |
| `page_url` | 页面链接 |
| `bidword_company_count` | 竞价公司数 |
| `long_keyword_count` | 长尾词数 |
| `index` | 流量指数（百度PC指数） |
| `mobile_index` | 百度移动指数 |
| `haosou_index` | 360指数 |
| `bidword_pcpv` | PC日检索量 |
| `bidword_recommendprice_avg` | 竞价参考价（推荐出价均价） |
| `bidword_wisepv` | 移动日检索量 |
| `toutiao_index` | 头条指数 |
| `douyin_index` | 抖音指数 |
| `kuai_shou_index` | 快手指数（注意字段名有下划线） |
| `google_index` | 谷歌指数 |
| `weibo_index` | 微博指数 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/keyword/baijiahao" \
  -H "Authorization: 你的APIKEY" \
  -d "keyword=百家号名称&platform=pc"
```
