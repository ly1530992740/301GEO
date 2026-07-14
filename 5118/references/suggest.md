# 下拉联想词挖掘 API

> 环境变量: `API_5118_SUGGEST`
> 介绍页: https://www.5118.com/apistore/detail/597e2193-9490-eb11-8daf-e4434bdf6706

## 基本信息

- **接口地址**: `https://apis.5118.com/suggest/list`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `word` | string | ✅ | 搜索母词 |
| `platform` | string | ✅ | 查询平台，可选值见下方 |

### platform 可选值

`baidu`, `baidumobile`, `shenma`, `360`, `360mobile`, `sogou`, `sogoumobile`, `zhihu`, `toutiao`, `taobao`, `tmall`, `pinduoduo`, `jingdong`, `douyin`, `amazon`, `xiaohongshu`

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": [
    {
      "word": "国庆假期",
      "promote_word": "国庆假期去哪玩",
      "platform": "zhihu",
      "add_time": "2022-09-24T11:28:10.027"
    }
  ]
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `word` | 搜索词 |
| `promote_word` | 平台返回的下拉联想词 |
| `platform` | 来源平台 |
| `add_time` | 数据获取时间 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/suggest/list" \
  -H "Authorization: 你的APIKEY" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "word=SEO&platform=baidu"
```
