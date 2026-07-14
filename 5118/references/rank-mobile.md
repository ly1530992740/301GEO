# 移动-排名查询 API（实时）

> 环境变量: `API_5118_RANK_MOBILE`
> 介绍页: https://www.5118.com/apistore/detail/9d211434-d3a2-e711-b5b0-d4ae52d0f72c

## 基本信息

- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## ⚠️ 异步两步接口（提交任务与获取结果使用同一地址）

### 步骤一：提交排名查询任务

- **接口地址**: `https://apis.5118.com/morerank/baidumobile`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 要查询排名的网址 |
| `keywords` | string | ✅ | - | 关键词，多个用"\|"隔开，单次上限50个 |
| `checkrow` | int | ❌ | 50 | 检测前n名，最大100 |

### 步骤二：获取检测结果

- **接口地址**: `https://apis.5118.com/morerank/baidumobile`（同步骤一地址）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `taskid` | int | ✅ | 步骤一返回的任务ID |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": {
    "taskid": 123456,
    "keywordmonitor": [
      {
        "keyword": "SEO优化",
        "search_engine": "baidumobile",
        "ip": "1.2.3.4",
        "area": "广东",
        "network": "电信",
        "ranks": [
          {
            "site_url": "www.example.com",
            "rank": 1,
            "page_title": "SEO优化教程",
            "page_url": "https://www.example.com/seo",
            "top100": 5200,
            "site_weight": 6
          }
        ]
      }
    ]
  }
}
```

## 返回字段说明

### 外层字段（keywordmonitor 数组中的每个元素）

| 字段 | 说明 |
|------|------|
| `keyword` | 关键词 |
| `search_engine` | 搜索引擎类型（baidumobile） |
| `ip` | 查询使用的IP |
| `area` | 查询地区 |
| `network` | 网络类型 |
| `ranks` | 排名结果集合（数组） |

### ranks 内层字段（每条排名记录）

| 字段 | 说明 |
|------|------|
| `site_url` | 网站地址 |
| `rank` | 排名（0表示未入围） |
| `page_title` | 页面标题 |
| `page_url` | 页面链接 |
| `top100` | 该域名Top100词量 |
| `site_weight` | 5118权重 |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/morerank/baidumobile" \
  -H "Authorization: 你的APIKEY" \
  -d "url=www.example.com&keywords=SEO|关键词&checkrow=50"
```
