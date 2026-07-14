# PC-URL收录检测 API

> 环境变量: `API_5118_INCLUDE`
> 介绍页: https://www.5118.com/apistore/detail/f18cc2ae-8ea2-e711-b5b0-d4ae52d0f72c

## 基本信息

- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## ⚠️ 异步两步接口（提交任务与获取结果使用同一地址）

### 步骤一：提交检测任务

- **接口地址**: `https://apis.5118.com/include`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `urls` | string | ✅ | 要检测的网址，多个用"\|"隔开，最多200个 |

**返回：** `taskid`（任务ID）、`total`（提交总数）

### 步骤二：获取检测结果

- **接口地址**: `https://apis.5118.com/include`（同步骤一地址）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `taskid` | int | ✅ | 步骤一返回的任务ID |

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `check_status` | 检测状态：0-检测中, 1-完成 |
| `data[].url` | 检测的URL |
| `data[].include_status` | 收录状态：0-未收录, 1-已收录, 2-检测失败 |

## 调用示例

```bash
# 步骤一
curl -X POST "https://apis.5118.com/include" \
  -H "Authorization: 你的APIKEY" \
  -d "urls=https://www.example.com/page1|https://www.example.com/page2"

# 步骤二
curl -X POST "https://apis.5118.com/include" \
  -H "Authorization: 你的APIKEY" \
  -d "taskid=123456"
```
