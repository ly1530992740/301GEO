# 移动流量词挖掘 API

> 环境变量: `API_5118_TRAFFIC`
> 介绍页: https://www.5118.com/apistore/detail/540c9870-b2b9-e911-80d2-1866da4dbcc0

## 基本信息

- **接口地址**: `https://apis.5118.com/traffic`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## ⚠️ 异步两步接口

此接口为实时挖掘，通常1-10分钟内返回结果。分为两步调用。

### 步骤一：提交挖掘任务

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keyword` | string | ✅ | 待挖掘的关键词 |

**返回：**
```json
{
  "errcode": "200104",
  "errmsg": "数据获取中",
  "taskid": 123456
}
```

### 步骤二：获取挖掘结果

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `taskid` | int | ✅ | - | 步骤一返回的任务ID |
| `keyword` | string | ✅ | - | 关键词 |
| `page_index` | int | ❌ | 1 | 当前分页 |
| `page_size` | int | ❌ | 20 | 每页数量（最大500） |

**返回示例（任务完成）：**
```json
{
  "errcode": "0",
  "errmsg": "",
  "taskid": 123456,
  "total": 1500,
  "page_count": 75,
  "page_index": 1,
  "page_size": 20,
  "data": [
    {
      "word": "SEO教程",
      "weight": 85,
      "mobile_index": 230,
      "bidword_wisepv": 340
    }
  ]
}
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `word` | 流量词 |
| `weight` | 价值量 |
| `mobile_index` | 移动指数 |
| `bidword_wisepv` | 移动日检索量 |

## 调用流程

```
1. POST { keyword: "SEO" }
   → 获取 taskid，errcode=200104 表示数据获取中

2. 等待 1-10 分钟

3. POST { taskid: 123456, keyword: "SEO", page_index: 1, page_size: 20 }
   → errcode=200104: 继续等待
   → errcode=0: 获取结果
```
