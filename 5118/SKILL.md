---
name: 5118-data
description: 5118 工具集 — 关键词挖掘、排名查询、排名词导出、竞价词查询、收录检测、权重查询、备案查询、内容改写、AI检测、违规词检测等
---

# 5118 API 工具集

## 认证方式

所有接口通过 HTTP Header `Authorization` 携带 APIKEY：

```
Authorization: 你的APIKEY
```

> APIKEY 直接作为 Header 值，**无需** "Bearer" 或 "APISTORE" 前缀。

## 通用请求规范

- **Content-Type**: `application/x-www-form-urlencoded; charset=utf-8`
- **请求方式**: 全部 `POST`
- **返回格式**: JSON，`errcode` 为 `"0"` 时表示成功
- **编码处理**: 请求参数中的中文必须进行 **URL 编码**（UrlEncode）；响应中的字段可能包含 **URL 编码的中文**，必须进行 **URL 解码**（UrlDecode）后再展示给用户

## API Key 注册表

每个接口使用**独立 APIKEY**，在 `openclaw.json` 的 `env` 中配置：

```json
{
  "env": {
    "API_5118_LONGTAIL_V2": "海量长尾词挖掘v2的Key",
    "API_5118_FREQ_WORDS": "细分行业分析的Key",
    "API_5118_SUGGEST": "下拉联想词挖掘的Key",
    "API_5118_KW_PARAM_V2": "关键词搜索量信息v2的Key",
    "API_5118_TAOBAO": "淘宝长尾词挖掘的Key",
    "API_5118_JD": "京东长尾词挖掘的Key",
    "API_5118_PDD": "拼多多长尾词挖掘的Key",
    "API_5118_SM": "神马长尾词挖掘的Key",
    "API_5118_GOOGLE": "Google长尾词挖掘的Key",
    "API_5118_AMAZON": "亚马逊长尾词挖掘的Key",
    "API_5118_TRAFFIC": "移动流量词挖掘的Key",
    "API_5118_BAIDUPC_V2": "PC网站排名词导出v2的Key",
    "API_5118_BAIJIAHAO": "百家号排名词导出的Key",
    "API_5118_MOBILE_V2": "移动网站排名词导出v2的Key",
    "API_5118_DOMAIN_V2": "PC整站排名词导出v2的Key",
    "API_5118_BIDSITE": "竞价推广公司挖掘的Key",
    "API_5118_BIDWORD_V2": "网站竞价词挖掘v2的Key",
    "API_5118_RANK_PC": "PC排名查询的Key",
    "API_5118_RANK_MOBILE": "移动排名查询的Key",
    "API_5118_KWRANK_PC": "PC前50网站信息的Key",
    "API_5118_KWRANK_MOBILE": "移动前50网站信息的Key",
    "API_5118_INCLUDE": "URL收录检测的Key",
    "API_5118_WEIGHT": "网站权重查询的Key",
    "API_5118_ICP": "备案数据查询的Key",
    "API_5118_ICP_INSTANT": "即时备案数据查询的Key",
    "API_5118_REWRITE": "一键智能改写的Key",
    "API_5118_SENIOR_REWRITE": "一键改写升级版的Key",
    "API_5118_AKEY": "一键换词的Key",
    "API_5118_COREWORD": "智能核心词提取的Key",
    "API_5118_BANNEDWORD": "智能违规词检测的Key",
    "API_5118_EXPANDER": "文本扩写精灵的Key",
    "API_5118_SENTENCE": "整句智能原创的Key",
    "API_5118_TITLE": "智能标题生成的Key",
    "API_5118_ABSTRACT": "智能摘要提取的Key",
    "API_5118_SIM": "相似度检测的Key",
    "API_5118_AIDETECT": "AI内容检测器的Key",
    "API_5118_TITLEOPTIMIZER": "标题助手的Key",
    "API_5118_ARTICLEWRITER": "段落组合大师的Key"
  }
}
```

## 路由表

| 用户意图 | 接口名称 | 参考文件 | 环境变量 |
|---------|---------|---------|---------|
| 长尾词/关键词拓展 | 海量长尾词挖掘v2 | `references/longtail-keyword-v2.md` | `API_5118_LONGTAIL_V2` |
| 细分行业/高频词分析 | 细分行业分析 | `references/frequency-words.md` | `API_5118_FREQ_WORDS` |
| 下拉联想/搜索建议 | 下拉联想词挖掘 | `references/suggest.md` | `API_5118_SUGGEST` |
| 关键词搜索量/指数查询 | 关键词搜索量信息v2 | `references/keyword-param-v2.md` | `API_5118_KW_PARAM_V2` |
| 淘宝关键词 | 淘宝长尾词挖掘 | `references/taobao-keyword.md` | `API_5118_TAOBAO` |
| 京东关键词 | 京东长尾词挖掘 | `references/jd-keyword.md` | `API_5118_JD` |
| 拼多多关键词 | 拼多多长尾词挖掘 | `references/pdd-keyword.md` | `API_5118_PDD` |
| 神马搜索关键词 | 神马长尾词挖掘 | `references/sm-keyword.md` | `API_5118_SM` |
| Google/谷歌关键词 | Google长尾词挖掘 | `references/google-keyword.md` | `API_5118_GOOGLE` |
| 亚马逊/跨境电商 | 亚马逊长尾词挖掘 | `references/amazon-keyword.md` | `API_5118_AMAZON` |
| 移动流量词 | 移动流量词挖掘 | `references/traffic-dig.md` | `API_5118_TRAFFIC` |
| 网站PC排名词 | PC-网站排名词导出v2 | `references/baidupc-rank-v2.md` | `API_5118_BAIDUPC_V2` |
| 百家号排名 | 百家号排名词导出 | `references/baijiahao-rank.md` | `API_5118_BAIJIAHAO` |
| 移动端排名词 | 移动-网站排名词导出v2 | `references/mobile-rank-v2.md` | `API_5118_MOBILE_V2` |
| 整站排名词 | PC-整站排名词导出v2 | `references/domain-rank-v2.md` | `API_5118_DOMAIN_V2` |
| 竞价推广公司 | 竞价推广公司挖掘 | `references/bid-site.md` | `API_5118_BIDSITE` |
| 网站竞价词 | 网站竞价词挖掘v2 | `references/bidword-v2.md` | `API_5118_BIDWORD_V2` |
| PC排名查询（实时） | PC-排名查询 | `references/rank-pc.md` | `API_5118_RANK_PC` |
| 移动排名查询（实时） | 移动-排名查询 | `references/rank-mobile.md` | `API_5118_RANK_MOBILE` |
| PC前50网站排名 | PC-前50网站信息 | `references/kwrank-pc.md` | `API_5118_KWRANK_PC` |
| 移动前50网站排名 | 移动-前50网站信息 | `references/kwrank-mobile.md` | `API_5118_KWRANK_MOBILE` |
| URL收录检测 | PC-URL收录检测 | `references/include.md` | `API_5118_INCLUDE` |
| 网站权重查询 | 网站5118权重查询 | `references/weight.md` | `API_5118_WEIGHT` |
| 备案查询 | 备案数据查询 | `references/icp.md` | `API_5118_ICP` |
| 即时备案查询 | 即时备案数据查询 | `references/icp-instant.md` | `API_5118_ICP_INSTANT` |
| 文章改写/伪原创 | 一键智能改写 | `references/rewrite.md` | `API_5118_REWRITE` |
| 改写升级版 | 一键改写升级版 | `references/senior-rewrite.md` | `API_5118_SENIOR_REWRITE` |
| 换词/同义词替换 | 一键换词 | `references/akey.md` | `API_5118_AKEY` |
| 核心词提取 | 智能核心词提取 | `references/coreword.md` | `API_5118_COREWORD` |
| 违规词检测/广告法 | 智能违规词检测 | `references/bannedword.md` | `API_5118_BANNEDWORD` |
| 文本扩写 | 文本扩写精灵 | `references/expander.md` | `API_5118_EXPANDER` |
| 整句原创/句子改写 | 整句智能原创 | `references/sentence.md` | `API_5118_SENTENCE` |
| 智能标题/标题生成 | 智能标题生成 | `references/title.md` | `API_5118_TITLE` |
| 文章摘要 | 智能摘要提取 | `references/abstract.md` | `API_5118_ABSTRACT` |
| 文本相似度 | 相似度检测 | `references/sim.md` | `API_5118_SIM` |
| AI内容检测 | AI内容检测器 | `references/aidetect.md` | `API_5118_AIDETECT` |
| 标题优化/标题助手 | 标题助手 | `references/titleoptimizer.md` | `API_5118_TITLEOPTIMIZER` |
| 段落组合/文章生成 | 段落组合大师 | `references/articlewriter.md` | `API_5118_ARTICLEWRITER` |


## 通用错误码

参见 `references/error-codes.md`

## 执行步骤

1. 识别用户意图 → 匹配路由表
2. 检查对应环境变量是否已配置，缺失则**停下来询问**
3. 加载 `references/` 下对应文件获取接口详情
4. 构造 POST 请求（form-urlencoded），设置 Authorization Header
5. **编码处理**：请求参数中的中文必须进行 URL 编码（UrlEncode）
6. 发送到 `https://apis.5118.com/...` 对应端点
7. **解码处理**：解析 JSON 返回后，对所有字符串字段进行 URL 解码（UrlDecode / `urllib.parse.unquote`），将 `%XX` 转为可读中文后再展示给用户

### 编码处理示例

```python
import requests
from urllib.parse import unquote

resp = requests.post(
    "https://apis.5118.com/keyword/word/v2",
    headers={"Authorization": "APIKEY"},
    data={"keyword": "SEO优化"}
).json()

# 重要：对返回的字符串字段进行 URL 解码
if resp["errcode"] == "0":
    for item in resp["data"]["word"]:
        keyword = unquote(str(item.get("keyword", "")))
        print(keyword)
```
