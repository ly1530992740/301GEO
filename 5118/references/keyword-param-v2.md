# 关键词搜索量信息 API v2

> 环境变量: `API_5118_KW_PARAM_V2`
> 介绍页: https://www.5118.com/apistore/detail/90f3d6ed-2b12-ed11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/keywordparam/v2`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded; charset=utf-8`
- **认证**: Header `Authorization: 你的APIKEY`

## ⚠️ 异步两步接口

此接口采用异步模式，分为两步调用，**提交任务和获取结果使用同一个接口地址**，程序根据传入参数自动判断：

### 步骤一：提交查询任务

- **接口地址**: `https://apis.5118.com/keywordparam/v2`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keywords` | string | ✅ | 关键词，多个用 `\|` 隔开，一次最多50个 |

**返回示例：**
```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "taskid": 40724567
  }
}
```

### 步骤二：获取检测结果

- **接口地址**: `https://apis.5118.com/keywordparam/v2`（同步骤一地址）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `taskid` | int/string | ✅ | 步骤一返回的任务ID |

> 若返回 errcode `101` 表示任务处理中，建议间隔 10 秒后重试。

**返回示例（实际测试数据）：**
```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "taskid": 40724567,
    "keyword_param": [
      {
        "keyword": "SEO优化",
        "index": 299,
        "mobile_index": 197,
        "haosou_index": 0,
        "bidword_kwc": 1,
        "bidword_pcpv": 117,
        "bidword_wisepv": 120,
        "long_keyword_count": 174908,
        "bidword_price": 2.38,
        "bidword_company_count": 590,
        "toutiao_index": 5,
        "douyin_index": 674,
        "bidword_recommendprice_min": 0.55,
        "bidword_recommendprice_max": 21.04,
        "age_best": "30-39",
        "age_best_value": 60.22,
        "sex_male": 81.08,
        "sex_female": 18.92,
        "bidword_showreasons": "",
        "bidword_recommend_price_avg": 4.54,
        "google_index": 0,
        "kuaishou_index": 0,
        "weibo_index": 0
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
| `bidword_kwc` | 竞价激烈程度（1-高, 2-中, 3-低） |
| `bidword_pcpv` | PC日检索量 |
| `bidword_wisepv` | 移动日检索量 |
| `long_keyword_count` | 长尾词个数 |
| `bidword_price` | SEM点击价格 |
| `bidword_company_count` | 竞价公司数量 |
| `toutiao_index` | 头条指数 |
| `douyin_index` | 抖音指数 |
| `bidword_recommendprice_min` | 竞价推荐最低价 |
| `bidword_recommendprice_max` | 竞价推荐最高价 |
| `age_best` | 最关注年龄段 |
| `age_best_value` | 最关注年龄段占比 |
| `sex_male` | 男性用户比例 |
| `sex_female` | 女性用户比例 |
| `bidword_showreasons` | 竞价展示原因/流量特点 |
| `bidword_recommend_price_avg` | 竞价推荐出价均价 |
| `google_index` | 谷歌指数 |
| `kuaishou_index` | 快手指数 |
| `weibo_index` | 微博指数 |

## 调用流程

```
1. POST https://apis.5118.com/keywordparam/v2
   Body: keywords=SEO优化|关键词挖掘|网站排名
   → 获取 taskid

2. 等待 5~10 秒

3. POST https://apis.5118.com/keywordparam/v2
   Body: taskid=40724567
   → 如果 errcode=101，继续等待重试
   → 如果 errcode=0，获取到结果
```
