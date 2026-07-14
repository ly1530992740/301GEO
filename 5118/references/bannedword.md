# 智能违规词检测 API

> 环境变量: `API_5118_BANNEDWORD`
> 介绍页: https://www.5118.com/apistore/detail/10cfa523-5545-ee11-8da8-e43d1a103141

## 基本信息

- **接口地址**: `https://apis.5118.com/bannedword/v2`
- **请求方式**: POST
- **Content-Type**: `application/x-www-form-urlencoded`
- **认证**: Header `Authorization: 你的APIKEY`

## 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `txt` | string | ✅ | 需检测的文本，**值必须进行 UrlEncode 编码** |

## 返回示例

```json
{
  "errcode": "0",
  "errmsg": "",
  "data": [
    {
      "levelName": "不通过",
      "item": [
        {
          "word": "最好",
          "labelName": "广告法",
          "secondLabelName": "极限词汇"
        }
      ]
    }
  ]
}
```

## 返回字段

| 字段 | 说明 |
|------|------|
| `data[].levelName` | 违规等级（"不通过"/"可疑"） |
| `data[].item[].word` | 违规词 |
| `data[].item[].labelName` | 违规分类（如"广告法"） |
| `data[].item[].secondLabelName` | 违规子分类（如"极限词汇"） |

## 调用示例

```bash
curl -X POST "https://apis.5118.com/bannedword/v2" \
  -H "Authorization: 你的APIKEY" \
  -d "txt=这是最好的产品"
```
