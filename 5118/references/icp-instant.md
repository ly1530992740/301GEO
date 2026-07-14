# 即时备案数据查询 API

> 环境变量: `API_5118_ICP_INSTANT`
> 介绍页: https://www.5118.com/apistore/detail/adc94d7c-6464-ea11-8da2-20040ff9d71d

## 基本信息

- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## ⚠️ 异步两步接口（提交任务与获取结果使用同一地址）

### 步骤一：提交查询任务

- **接口地址**: `https://apis.5118.com/icp/instant`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `searchtext` | string | ✅ | 需要查询的域名 |

**返回：** `taskid`

### 步骤二：获取查询结果

- **接口地址**: `https://apis.5118.com/icp/instant`（同步骤一地址）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `taskid` | int | ✅ | 步骤一返回的任务ID |

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `company_name` | 企业名称 |
| `company_type` | 企业类型 |
| `icp_license` | 备案号 |
| `main_page` | 首页 |
| `site_name` | 网站名称 |
| `owner` | 负责人 |

## 调用示例

```bash
# 步骤一
curl -X POST "https://apis.5118.com/icp/instant" \
  -H "Authorization: 你的APIKEY" \
  -d "searchtext=example.com"

# 步骤二
curl -X POST "https://apis.5118.com/icp/instant" \
  -H "Authorization: 你的APIKEY" \
  -d "taskid=123456"
```
