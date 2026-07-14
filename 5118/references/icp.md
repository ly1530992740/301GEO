# 备案数据查询 API

> 环境变量: `API_5118_ICP`
> 介绍页: https://www.5118.com/apistore/detail/e63e8855-7a60-ea11-8da2-20040ff9d71d

## 基本信息

- **接口地址**: `https://apis.5118.com/icp/getinfo`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `searchtext` | string | ✅ | 域名、备案号、网站名称或主办单位名称 |
| `searchtype` | string | ❌ | 查询类型：`domain`(域名), `icp`(备案号), `name`(网站名称), `company`(主办单位) |

## 返回字段说明

| 字段 | 说明 |
|------|------|
| `data.subject` | 主办单位信息（名称、性质、备案号） |
| `data.webList` | 网站列表（名称、首页、备案号） |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/icp/getinfo" \
  -H "Authorization: 你的APIKEY" \
  -d "searchtext=example.com&searchtype=domain"
```
