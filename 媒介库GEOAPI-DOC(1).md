# 媒介库网 - 下游代理 API 对接文档

> **版本**：v1.0  
> **基础地址**：`https://api.meijieku.com`（请替换为实际域名）  
> **数据格式**：JSON  
> **编码**：UTF-8

---

## 通用说明

**请求头**

| Header          | 说明                    | 必填 |
| --------------- | ----------------------- | ---- |
| `Content-Type`  | `application/json`      | 是   |
| `Authorization` | JWT Token（登录后获取） | 是   |

**通用响应结构**

```json
{
    "status": 200,
    "msg": "操作描述",
    "data": {}
}
```

- `status` = 200 表示成功，103 表示未登录/Token无效，411 表示 Token 过期

**获取 Token**

调用 `POST /api/System/login_long_token`，传入 `mobile`（手机号）和 `password`（密码），返回有效期 1 年的 Token：

```json
// 请求
{ "mobile": "13800138000", "password": "your_password" }

// 响应
{ "status": 200, "data": { "token": "eyJhbGci..." }, "msg": "登录成功" }
```

后续所有接口在 Header 中携带 `Authorization: {token}` 即可。

---

## 接口一：获取媒体资源列表

获取可发稿的自媒体和门户网站媒体列表，包含媒体类型、站点、名称、价格等信息。

- **自媒体**：`POST /api/Resource/Wemedia/list`
- **网站媒体**：`POST /api/Resource/Website/list`
- **短视频**：`POST /api/Resource/Shortvideo/list`
- **问答**：`POST /api/Resource/Question/list`
- **代写**：`POST /api/Resource/Ghostwrite/list`

### 请求参数

| 参数        | 类型   | 必填 | 说明                            |
| ----------- | ------ | ---- | ------------------------------- |
| `pageNo`    | int    | 否   | 页码，默认 1                    |
| `pageSize`  | int    | 否   | 每页条数，默认 20               |

### 请求示例

```json
{
    "pageNo": 1,
    "pageSize": 20
}
```

### 响应示例

```json
{
    "status": 200,
    "data": {
        "total": 1500,
        "per_page": 20,
        "current_page": 1,
        "last_page": 75,
        "data": [
            {
                "resource_id": 75564,
                "title": "中国日报网科技滚动",
                "price_1": "95.00",
                "price_2": "95.00",
                "price_3": "95.00",
                "remarks": "好出稿，不需要来源，页面有科技滚动频道显示，上稿请确认好稿件，不删撤稿",
                "case_link": "https://cnews.chinadaily.com.cn/a/202411/28/WS67483428a310b59111da6162.html",
                "field_1": 1001,
                "field_3": 3001,
                "field_5": 5003,
                "field_6": 6001,
                "field_9": "",
                "pc_weigh": 4,
                "wap_weigh": 4,
                "entrance_link": null,
                "publish_rate": 65,
                "publish_time": 34444,
                "type": 3,
                "is_collect": 1,
                "is_blacklist": 0,
                "price_type": null,
                "field_1_name": "IT科技",
                "field_3_name": "综合全国",
                "field_5_name": "不包资讯收录",
                "field_6_name": "不可带网址"
            }
        ]
    }
}
```

### 响应字段

> 可对比官网展示数据。

---

## 接口二：提交稿件

将稿件通过 API 上传至媒介库网进行发稿。

- **自媒体发稿**：`POST /api/Article/Wemedia/add`
- **网站媒体发稿**：`POST /api/Article/Website/add`
- **短视频发稿**：`POST /api/Article/ShortVideo/add`
- **问答发稿**：`POST /api/Article/Question/add`
- **代写发稿**：`POST /api/Article/Ghostwrite/add`

### 请求参数

| 参数         | 类型   | 必填 | 说明                                            |
| ------------ | ------ | ---- | ----------------------------------------------- |
| `title_type` | int    | 是   | 0=每个资源独立标题，1=统一标题                  |
| `title`      | string | 是   | 稿件标题（title_type=1 时为统一标题）           |
| `content`    | string | 是   | 稿件内容（HTML 格式）                           |
| `remark`     | string | 否   | 备注                                            |
| `customer`   | string | 否   | 客户标识（自行区分用途）                        |
| `resource`   | array  | 是   | 投放资源列表                                    |

**`resource` 数组元素**：

| 字段          | 类型   | 必填 | 说明                                   |
| ------------- | ------ | ---- | -------------------------------------- |
| `resource_id` | int    | 是   | 资源ID（来自接口一）                   |
| `name`        | string | 是   | 资源名称（来自接口一的 `title` 字段）  |
| `title`       | string | 否   | 单独标题（title_type=0 时使用）        |

### 请求示例

```json
{
    "title_type": 1,
    "title": "2024年人工智能行业发展趋势分析",
    "content": "<p>正文内容...</p>",
    "remark": "请尽快安排发布",
    "customer": "客户A",
    "resource": [
        { "resource_id": 10001, "name": "XX财经号", "title": "" },
        { "resource_id": 10002, "name": "YY科技号", "title": "" }
    ]
}
```

### 响应示例

```json
{
    "status": 200,
    "msg": "提交成功",
    "data": true,
    "result": [
        { "article_id": 50001, "order_id": "002202401151234567890" },
        { "article_id": 50002, "order_id": "002202401151234567891" }
    ]
}
```

### 响应字段

| 字段         | 类型   | 说明                         |
| ------------ | ------ | ---------------------------- |
| `article_id` | int    | 稿件ID（用于查询状态）       |
| `order_id`   | string | 订单号                       |

> **注意**：提交即扣费（从账户余额扣除），每个 resource 生成独立订单，10秒内禁止重复提交。

---

## 接口三：查询稿件状态

实时查询已提交稿件的处理状态。

- **自媒体稿件**：`POST /api/Article/Wemedia/list`
- **门户网站稿件**：`POST /api/Article/Website/list`
- **短视频稿件**：`POST /api/Article/ShortVideo/list`
- **问答稿件**：`POST /api/Article/Question/list`
- **代写稿件**：`POST /api/Article/Ghostwrite/list`

### 请求参数

| 参数             | 类型   | 必填 | 说明                                           |
| ---------------- | ------ | ---- | ---------------------------------------------- |
| `pageNo`         | int    | 否   | 页码，默认 1                                   |
| `pageSize`       | int    | 否   | 每页条数，默认 10                              |
| `order_id`       | string | 否   | 订单号（精确查询）                             |
| `title`          | string | 否   | 稿件标题（模糊搜索）                           |
| `resource_title` | string | 否   | 媒体名称（模糊搜索）                           |
| `customer`       | string | 否   | 客户标识                                       |
| `status`         | mixed  | 否   | 状态码筛选，传 `all` 或空=查全部               |
| `create_time`    | array  | 否   | 创建时间范围 `[开始时间戳, 结束时间戳]`（毫秒）|
| `release_time`   | array  | 否   | 发布时间范围 `[开始时间戳, 结束时间戳]`（毫秒）|

### 请求示例

```json
{
    "pageNo": 1,
    "pageSize": 10,
    "order_id": "002202401151234567890"
}
```

### 响应示例

```json
{
    "status": 200,
    "data": {
        "total": 100,
        "per_page": 10,
        "current_page": 1,
        "last_page": 10,
        "data": [
            {
                "article_id": 50001,
                "order_id": "002202401151234567890",
                "resource_title": "XX财经号",
                "title": "2024年人工智能行业发展趋势分析",
                "price": "150.00",
                "customer": "客户A",
                "status": 2,
                "link": "https://www.toutiao.com/article/xxxxxxx",
                "refund_info": null,
                "rejection_info": null,
                "release_time": 1705312000,
                "create_time": 1705300000
            }
        ],
        "status": { "0": 10, "1": 5, "2": 80, "4": 5 }
    }
}
```

### 状态码说明

| status | 含义     | 说明                               |
| ------ | -------- | ---------------------------------- |
| **0**  | 待处理   | 等待编辑处理                       |
| **1**  | 已收稿   | 编辑已接收，正在安排发布           |
| **2**  | 已发布   | **发稿成功**                       |
| **4**  | 已退款   | **发稿失败**，款项已退回余额       |
| **9**  | 售后中   | 售后处理中                         |

---

## 接口四：获取稿件URL / 失败原因

> 本接口与接口三使用**同一端点**，通过返回字段中的 `link`、`refund_info`、`rejection_info` 获取结果。

- **自媒体稿件**：`POST /api/Article/Wemedia/list`
- **门户网站稿件**：`POST /api/Article/Website/list`
- **短视频稿件**：`POST /api/Article/ShortVideo/list`
- **问答稿件**：`POST /api/Article/Question/list`
- **代写稿件**：`POST /api/Article/Ghostwrite/list`

### 结果判断

| 场景         | 判断条件     | 读取字段                                    |
| ------------ | ------------ | ------------------------------------------- |
| **发稿成功** | `status == 2` | `link` — 稿件发布的 URL                    |
| **发稿失败** | `status == 4` | `refund_info` 或 `rejection_info` — 失败原因 |
| **处理中**   | `status == 0 或 1` | 稍后重新查询                          |
| **售后中**   | `status == 9` | 售后处理中，等待结果                        |

### 关键响应字段

| 字段             | 类型   | 说明                                         |
| ---------------- | ------ | -------------------------------------------- |
| `article_id`     | int    | 稿件ID                                      |
| `order_id`       | string | 订单号                                       |
| `status`         | int    | 稿件状态码                                   |
| `link`           | string | 发布链接（status=2 时有值）                  |
| `refund_info`    | string | 撤稿/退款原因（status=4 时有值）             |
| `rejection_info` | string | 拒稿原因（status=4 时有值）                  |
| `release_time`   | int    | 发布时间（Unix 时间戳）                      |

### 代码示例

```javascript
// 轮询查询稿件结果
const article = response.data.data[0];

if (article.status === 2) {
    // ✅ 发稿成功
    console.log("发布链接:", article.link);
} else if (article.status === 4) {
    // ❌ 发稿失败
    console.log("失败原因:", article.refund_info || article.rejection_info);
} else {
    // ⏳ 处理中（status=0/1/9），建议 5~10 分钟后重试
}
```

---

## 常见错误

| msg                          | 说明             |
| ---------------------------- | ---------------- |
| `请登录后重试！`             | Token 缺失或无效 |
| `余额不足！`                | 账户余额不足     |
| `请勿重复提交，请稍后再试`  | 10秒防重复限制   |
| `尚未选择任何资源`           | resource 为空    |
| `稿件标题不能为空`           | title 缺失       |
| `稿件内容不能为空`           | content 缺失     |
