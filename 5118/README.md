# 5118 API 工具集 — 使用说明

## 📖 概述

本 Skill 封装了 5118 平台对外公开的 **38 个 API 接口**，涵盖关键词挖掘、排名查询、网站分析、内容创作与内容检测五大类。智能体可通过本 Skill 直接调用 5118 的公开 API 获取数据。

> **重要提示**：所有接口需要先在 [5118 API 商城](https://www.5118.com/apistore) 购买对应的 API 套餐并获取 APIKEY 后才能使用。

---

## 🚀 快速开始

### 1. 获取 APIKEY

1. 登录 [5118.com](https://www.5118.com)
2. 进入 [API 商城](https://www.5118.com/apistore)
3. 选择需要的 API → 点击购买套餐
4. 购买完成后在「我的 API」中获取对应的 **APIKEY**

### 2. 配置环境变量

在 `openclaw.json`（或你使用的智能体配置文件）的 `env` 字段中填入 APIKEY：

```json
{
  "env": {
    "API_5118_LONGTAIL_V2": "你从5118获取的APIKEY",
    "API_5118_REWRITE": "你从5118获取的另一个APIKEY"
  }
}
```

> 💡 不需要配置全部 38 个 Key。**只配置你购买了的接口的 Key 即可**，未配置的接口在调用时会提示你先配置。

### 完整环境变量对照表

| 环境变量名 | 对应接口 | API 地址 |
|-----------|---------|---------|
| `API_5118_LONGTAIL_V2` | 海量长尾词挖掘v2 | `/keyword/word/v2` |
| `API_5118_FREQ_WORDS` | 细分行业分析 | `/tradeseg` |
| `API_5118_SUGGEST` | 下拉联想词挖掘 | `/suggest/list` |
| `API_5118_KW_PARAM_V2` | 关键词搜索量信息v2 | `/keywordparam/v2` |
| `API_5118_TAOBAO` | 淘宝长尾词挖掘 | `/keyword/taobao` |
| `API_5118_JD` | 京东长尾词挖掘 | `/keyword/jd` |
| `API_5118_PDD` | 拼多多长尾词挖掘 | `/keyword/pinduoduo` |
| `API_5118_SM` | 神马长尾词挖掘 | `/keyword/sm/word` |
| `API_5118_GOOGLE` | Google长尾词挖掘 | `/keyword/google` |
| `API_5118_AMAZON` | 亚马逊长尾词挖掘 | `/keyword/amazon` |
| `API_5118_TRAFFIC` | 移动流量词挖掘 | `/traffic` |
| `API_5118_BIDSITE` | 竞价推广公司挖掘 | `/bidsite` |
| `API_5118_BAIDUPC_V2` | PC-网站排名词导出v2 | `/keyword/pc/v2` |
| `API_5118_BAIJIAHAO` | 百家号排名词导出 | `/keyword/baijiahao` |
| `API_5118_MOBILE_V2` | 移动-网站排名词导出v2 | `/keyword/mobile/v2` |
| `API_5118_DOMAIN_V2` | PC-整站排名词导出v2 | `/keyword/domain/v2` |
| `API_5118_BIDWORD_V2` | 网站竞价词挖掘v2 | `/bidword/v2` |
| `API_5118_RANK_PC` | PC-排名查询（实时） | `/morerank/baidupc` |
| `API_5118_RANK_MOBILE` | 移动-排名查询（实时） | `/morerank/baidumobile` |
| `API_5118_KWRANK_PC` | PC-前50网站信息 | `/keywordrank/baidupc` |
| `API_5118_KWRANK_MOBILE` | 移动-前50网站信息 | `/keywordrank/baidumobile` |
| `API_5118_WEIGHT` | 网站5118权重查询 | `/weight` |
| `API_5118_INCLUDE` | PC-URL收录检测 | `/include` |
| `API_5118_ICP` | 备案数据查询 | `/icp/getinfo` |
| `API_5118_ICP_INSTANT` | 即时备案数据查询 | `/icp/instant` |
| `API_5118_REWRITE` | 一键智能改写 | `/wyc/rewrite` |
| `API_5118_SENIOR_REWRITE` | 一键改写升级版 | `/wyc/seniorrewrite` |
| `API_5118_AKEY` | 一键换词 | `/wyc/akey` |
| `API_5118_SENTENCE` | 整句智能原创 | `/wyc/sentence` |
| `API_5118_EXPANDER` | 文本扩写精灵 | `/ai/autoexpander` |
| `API_5118_TITLE` | 智能标题生成 | `/wyc/title` |
| `API_5118_TITLEOPTIMIZER` | 标题助手 | `/ai/titleoptimizer` |
| `API_5118_ABSTRACT` | 智能摘要提取 | `/abstract` |
| `API_5118_ARTICLEWRITER` | 段落组合大师 | `/articlewriter` |
| `API_5118_SIM` | 相似度检测 | `/wyc/sim` |
| `API_5118_AIDETECT` | AI内容检测器 | `/aidetect` |
| `API_5118_BANNEDWORD` | 智能违规词检测 | `/bannedword/v2` |
| `API_5118_COREWORD` | 智能核心词提取 | `/coreword` |

### 3. 开始使用

直接用自然语言向智能体描述你的需求，它会自动匹配到对应的 API：

```
用户：帮我挖掘"SEO优化"的长尾词
用户：查一下 www.example.com 的百度PC排名词
用户：帮我改写这段文章：[文章内容]
用户：检测这段内容是不是AI写的
```

---

## 📡 通用调用规范

所有接口遵循统一的调用规范：

| 项目 | 说明 |
|------|------|
| **请求域名** | `https://apis.5118.com` |
| **请求方式** | `POST` |
| **Content-Type** | `application/x-www-form-urlencoded; charset=utf-8` |
| **认证方式** | 在 Header 中添加 `Authorization: 你的APIKEY`（直接填Key，无需Bearer前缀） |
| **返回格式** | JSON，`errcode` 为 `"0"` 表示成功 |

### 通用 curl 示例

```bash
curl -X POST "https://apis.5118.com/keyword/word/v2" \
  -H "Authorization: 你的APIKEY" \
  -H "Content-Type: application/x-www-form-urlencoded; charset=utf-8" \
  -d "keyword=SEO优化&page_index=1&page_size=10"
```

### 通用 Python 示例

```python
import requests

url = "https://apis.5118.com/keyword/word/v2"
headers = {
    "Authorization": "你的APIKEY",
    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"
}
data = {
    "keyword": "SEO优化",
    "page_index": 1,
    "page_size": 10
}

response = requests.post(url, headers=headers, data=data)
result = response.json()

if result["errcode"] == "0":
    for word in result["data"]["word"]:
        print(f"{word['keyword']}  流量指数: {word['index']}")
else:
    print(f"错误: {result['errmsg']}")
```

---

## 📋 API 一览表

### 一、关键词挖掘类（12个）

| 接口名称 | 调用地址 | 参考文档 | 类型 |
|---------|---------|---------|------|
| 海量长尾词挖掘v2 | `/keyword/word/v2` | [longtail-keyword-v2.md](references/longtail-keyword-v2.md) | 同步 |
| 细分行业分析 | `/tradeseg` | [frequency-words.md](references/frequency-words.md) | 同步 |
| 下拉联想词挖掘 | `/suggest/list` | [suggest.md](references/suggest.md) | 同步 |
| 关键词搜索量信息v2 | `/keywordparam/v2` | [keyword-param-v2.md](references/keyword-param-v2.md) | ⚡异步 |
| 淘宝长尾词挖掘 | `/keyword/taobao` | [taobao-keyword.md](references/taobao-keyword.md) | 同步 |
| 京东长尾词挖掘 | `/keyword/jd` | [jd-keyword.md](references/jd-keyword.md) | 同步 |
| 拼多多长尾词挖掘 | `/keyword/pinduoduo` | [pdd-keyword.md](references/pdd-keyword.md) | 同步 |
| 神马长尾词挖掘 | `/keyword/sm/word` | [sm-keyword.md](references/sm-keyword.md) | 同步 |
| Google长尾词挖掘 | `/keyword/google` | [google-keyword.md](references/google-keyword.md) | 同步 |
| 亚马逊长尾词挖掘 | `/keyword/amazon` | [amazon-keyword.md](references/amazon-keyword.md) | 同步 |
| 移动流量词挖掘 | `/traffic` | [traffic-dig.md](references/traffic-dig.md) | ⚡异步 |
| 竞价推广公司挖掘 | `/bidsite` | [bid-site.md](references/bid-site.md) | 同步 |

### 二、排名与排名词导出类（10个）

| 接口名称 | 调用地址 | 参考文档 | 类型 |
|---------|---------|---------|------|
| PC-网站排名词导出v2 | `/keyword/pc/v2` | [baidupc-rank-v2.md](references/baidupc-rank-v2.md) | 同步 |
| 百家号排名词导出 | `/keyword/baijiahao` | [baijiahao-rank.md](references/baijiahao-rank.md) | 同步 |
| 移动-网站排名词导出v2 | `/keyword/mobile/v2` | [mobile-rank-v2.md](references/mobile-rank-v2.md) | 同步 |
| PC-整站排名词导出v2 | `/keyword/domain/v2` | [domain-rank-v2.md](references/domain-rank-v2.md) | 同步 |
| 网站竞价词挖掘v2 | `/bidword/v2` | [bidword-v2.md](references/bidword-v2.md) | 同步 |
| PC-排名查询（实时） | `/morerank/baidupc` | [rank-pc.md](references/rank-pc.md) | ⚡异步 |
| 移动-排名查询（实时） | `/morerank/baidumobile` | [rank-mobile.md](references/rank-mobile.md) | ⚡异步 |
| PC-前50网站信息 | `/keywordrank/baidupc` | [kwrank-pc.md](references/kwrank-pc.md) | ⚡异步 |
| 移动-前50网站信息 | `/keywordrank/baidumobile` | [kwrank-mobile.md](references/kwrank-mobile.md) | ⚡异步 |
| 网站5118权重查询 | `/weight` | [weight.md](references/weight.md) | 同步 |

### 三、网站信息类（3个）

| 接口名称 | 调用地址 | 参考文档 | 类型 |
|---------|---------|---------|------|
| PC-URL收录检测 | `/include` | [include.md](references/include.md) | ⚡异步 |
| 备案数据查询 | `/icp/getinfo` | [icp.md](references/icp.md) | 同步 |
| 即时备案数据查询 | `/icp/instant` | [icp-instant.md](references/icp-instant.md) | ⚡异步 |

### 四、内容创作/改写类（9个）

| 接口名称 | 调用地址 | 参考文档 | 类型 |
|---------|---------|---------|------|
| 一键智能改写 | `/wyc/rewrite` | [rewrite.md](references/rewrite.md) | 同步 |
| 一键改写升级版 | `/wyc/seniorrewrite` | [senior-rewrite.md](references/senior-rewrite.md) | 同步 |
| 一键换词 | `/wyc/akey` | [akey.md](references/akey.md) | 同步 |
| 整句智能原创 | `/wyc/sentence` | [sentence.md](references/sentence.md) | 同步 |
| 文本扩写精灵 | `/ai/autoexpander` | [expander.md](references/expander.md) | 同步 |
| 智能标题生成 | `/wyc/title` | [title.md](references/title.md) | 同步 |
| 标题助手 | `/ai/titleoptimizer` | [titleoptimizer.md](references/titleoptimizer.md) | 同步 |
| 智能摘要提取 | `/abstract` | [abstract.md](references/abstract.md) | 同步 |
| 段落组合大师 | `/articlewriter` | [articlewriter.md](references/articlewriter.md) | 同步 |

### 五、内容检测类（4个）

| 接口名称 | 调用地址 | 参考文档 | 类型 |
|---------|---------|---------|------|
| 相似度检测 | `/wyc/sim` | [sim.md](references/sim.md) | 同步 |
| AI内容检测器 | `/aidetect` | [aidetect.md](references/aidetect.md) | 同步 |
| 智能违规词检测 | `/bannedword/v2` | [bannedword.md](references/bannedword.md) | 同步 |
| 智能核心词提取 | `/coreword` | [coreword.md](references/coreword.md) | 同步 |

---

## ⚡ 异步接口使用说明

部分接口标记为 **⚡异步**，表示需要两步调用：

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  步骤一：提交任务  │───►│  等待处理         │───►│  步骤二：获取结果  │
│  获取 taskid      │    │  间隔 60s 轮询    │    │  传入 taskid      │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 异步调用 Python 示例（以关键词搜索量为例）

```python
import requests
import time

API_KEY = "你的APIKEY"
headers = {"Authorization": API_KEY}

# 步骤一：提交任务
resp = requests.post(
    "https://apis.5118.com/keywordparam/v2",
    headers=headers,
    data={"keywords": "SEO优化|关键词挖掘|网站排名"}
)
task = resp.json()
taskid = task["data"]["taskid"]
print(f"任务已提交，taskid: {taskid}")

# 步骤二：轮询获取结果
for i in range(10):  # 最多重试10次
    time.sleep(10)   # 等待10秒
    resp = requests.post(
        "https://apis.5118.com/keywordparam/v2",  # 同一地址，传taskid获取结果
        headers=headers,
        data={"taskid": taskid}
    )
    result = resp.json()
    if result["errcode"] == "0":
        for kw in result["data"]["keyword_param"]:
            print(f"{kw['keyword']}  指数:{kw['index']}  移动:{kw['mobile_index']}")
        break
    else:
        print(f"第{i+1}次轮询，状态: {result['errmsg']}")
```

### 异步接口调用规则

> **所有异步接口的提交任务和获取结果使用同一个地址**，程序根据传入参数自动判断是提交任务还是获取结果：
> - 传入业务参数（如 `keywords`、`url`） → 提交任务，返回 `taskid`
> - 传入 `taskid` → 获取该任务的处理结果

---

## ❌ 错误码速查

### 通用错误码（100xxx）

| errcode | 含义 | 处理方式 |
|---------|------|---------|
| `0` | 成功 | — |
| `100101` | 调用次数不够 | 请到5118充值 |
| `100102` | 每秒调用量超限 | 降低调用频率 |
| `100103` | 每小时调用量超限 | 等待后重试 |
| `100104` | 每天调用量超限 | 次日重试 |
| `100202` | 请求缺少 APIKEY | 检查 Authorization Header |
| `100203` | 无效的 APIKEY | 检查 Key 是否正确 |
| `100208` | 请求方式不支持 | 确保使用 POST 方法 |
| `100403` | APIKEY 不正确 | 核对 Key 拼写 |

### 系统级错误码（200xxx）

| errcode | 含义 | 处理方式 |
|---------|------|---------|
| `200104` | 数据获取中 | 异步接口轮询中，等待后重试 |
| `200107` | 服务器超时 | 稍后重试 |
| `200201` | 传进参数为空 | 检查请求参数 |
| `200202` | 用户ID为空 | 检查认证信息 |
| `200204` | 请提交要查询的网址 | 补充 url 参数 |
| `200301` | 网址格式不正确 | 检查 url 格式 |
| `200401` | 关键词数量超限 | 单次最多50个 |
| `200500` | 内容长度超过5000字符 | 缩短内容 |

完整错误码和格式说明请参阅 [error-codes.md](references/error-codes.md)。

---

## 📂 目录结构

```
5118-data/
├── README.md              ← 你正在看的这份文档
├── SKILL.md               ← Skill 主入口（路由表 + Key注册表）
└── references/            ← 各接口的详细参考文档
    ├── error-codes.md     ← 通用错误码
    ├── longtail-keyword-v2.md
    ├── frequency-words.md
    ├── suggest.md
    ├── keyword-param-v2.md
    ├── taobao-keyword.md
    ├── jd-keyword.md
    ├── pdd-keyword.md
    ├── sm-keyword.md
    ├── google-keyword.md
    ├── amazon-keyword.md
    ├── traffic-dig.md
    ├── baidupc-rank-v2.md
    ├── baijiahao-rank.md
    ├── mobile-rank-v2.md
    ├── domain-rank-v2.md
    ├── bid-site.md
    ├── bidword-v2.md
    ├── rank-pc.md
    ├── rank-mobile.md
    ├── kwrank-pc.md
    ├── kwrank-mobile.md
    ├── include.md
    ├── weight.md
    ├── icp.md
    ├── icp-instant.md
    ├── rewrite.md
    ├── senior-rewrite.md
    ├── akey.md
    ├── coreword.md
    ├── bannedword.md
    ├── expander.md
    ├── sentence.md
    ├── title.md
    ├── abstract.md
    ├── sim.md
    ├── aidetect.md
    ├── titleoptimizer.md
    └── articlewriter.md
```

---

## 💡 常见使用场景

### 场景一：竞品关键词分析

```
1. 用「PC-网站排名词导出v2」获取竞品网站的排名词
2. 用「关键词搜索量信息v2」批量查询这些词的搜索量
3. 用「海量长尾词挖掘v2」拓展出更多长尾词
4. 用「细分行业分析」了解行业核心词分布
```

### 场景二：内容创作工作流

```
1. 用「段落组合大师」基于关键词生成初稿
2. 用「一键智能改写」或「一键换词」提升原创度
3. 用「相似度检测」验证改写前后的差异度
4. 用「智能标题生成」为文章配上吸引人的标题
5. 用「智能违规词检测」检查是否有广告法违规用语
6. 用「AI内容检测器」确认内容不会被判定为AI生成
```

### 场景三：电商选词

```
1. 用「淘宝/京东/拼多多长尾词挖掘」获取平台热门词
2. 用「下拉联想词挖掘」获取各平台下拉词
3. 用「海量长尾词挖掘v2」深度拓展
```

### 场景四：网站健康检查

```
1. 用「网站5118权重查询」查看各搜索引擎权重
2. 用「PC-URL收录检测」批量检测页面收录情况
3. 用「PC排名查询」实时监控核心词排名变化
4. 用「备案数据查询」验证网站备案信息
```
