# GEO 功能开发进度手册

更新时间：2026-07-01

## 当前目标

把项目从“GEO 文章生成与媒介库发布工具”升级为“GEO 售前分析、策略制定、内容生产、发布和监控工具”。

## 已完成基础能力

1. Qwen 联网搜索、来源链接分析、文章格式总结。
2. 根据分析结果生成 GEO 文章。
3. 媒介库资源同步、平台匹配、人工确认、文章发布、订单状态同步。
4. SerpApi Google Search 与 Google Trends 接入。
5. 趋势与同行分析报告，输出 Markdown、JSON、CSV。
6. 趋势分析搜索词改为优先由 Qwen 生成，适配不同目标市场语言。

## 本次新增功能

### 1. 竞品分析

入口：Streamlit 顶部标签页 `GEO 策略工具 -> 竞品分析`

输入：

- 城市/市场
- 行业
- 客户/品牌
- 核心词/商品名
- 竞品名称/商品名，可选
- 竞品官网 URL，可选
- 竞品 PDF 路径，可选

处理逻辑：

- Qwen 生成竞品研究计划。
- SerpApi Search 抓取竞品、产品、服务、评论、比较页面。
- SerpApi Trends 补充趋势信息。
- 可读取 PDF 文本摘要。
- Qwen 生成 Markdown 竞品分析报告。

输出：

- `output/strategy_reports/*/competitor_analysis.md`
- `output/strategy_reports/*/competitor_analysis_data.json`
- 数据库表：`strategy_reports`，`report_type=competitor`

当前限制：

- PDF 只做文本提取，不做 OCR。
- 官网 URL 第一版只作为资料输入和搜索上下文，不做深度整站爬取。
- 竞品信息不足时生成“待补充版报告”。

### 2. AI 可见度诊断

入口：`GEO 策略工具 -> AI可见度诊断`

输入：

- 城市/市场
- 行业
- 客户/品牌
- 核心词/商品名
- 竞品名称，可选
- 测试问题数

处理逻辑：

- Qwen 根据市场和行业自动生成模拟用户问题，不使用写死模板。
- Qwen 联网模拟用户提问。
- 统计客户品牌是否出现、竞品是否出现、客户出现位置、情绪倾向、引用来源。
- 生成 AI 可见度诊断报告。

输出：

- `output/strategy_reports/*/ai_visibility.md`
- `output/strategy_reports/*/ai_visibility_data.json`
- 数据库表：`strategy_reports`，`report_type=visibility`

当前限制：

- 第一版只使用 Qwen 模拟用户提问。
- DeepSeek、豆包、Gemini、Perplexity、Google AI Overview 等暂未接入。
- 当前统计依赖模型返回 JSON，后续需要增加更强的校验与容错。

### 3. 品牌定位与 GEO 内容策略

入口：`GEO 策略工具 -> 品牌定位策略`

输入：

- 城市/市场
- 行业
- 客户/品牌
- 核心词/商品名
- 客户优势/已有资料，可不完整
- 竞品名称，可选
- 客户官网 URL，可选
- 客户/竞品资料 PDF 路径，可选

处理逻辑：

- SerpApi Search 补充行业、竞品、评论、内容环境。
- 可读取 PDF 文本摘要。
- 资料不完整时仍生成“待补充版报告”。
- Qwen 输出定位、差异化卖点、证据库、FAQ、内容主题池、30 天执行建议。

输出：

- `output/strategy_reports/*/brand_strategy.md`
- `output/strategy_reports/*/brand_strategy_data.json`
- 数据库表：`strategy_reports`，`report_type=brand_strategy`

当前限制：

- 尚未和文章生成流程深度联动。
- 暂未自动生成可编辑的品牌知识库实体。
- 暂未生成 PPT/PDF 售前方案。

### 4. GEO 手动监控

入口：`GEO 策略工具 -> 手动监控`

输入：

- 监控名称
- 城市/市场
- 行业
- 客户/品牌
- 核心词/商品名
- 竞品名称，可选
- 监控问题数

处理逻辑：

- Qwen 自动生成本轮监控问题。
- Qwen 联网模拟用户提问。
- 统计客户品牌提及率、竞品出现次数、引用来源和风险点。
- 读取同一客户最近 5 次监控记录作为历史上下文。
- 输出手动监控报告。

输出：

- `output/strategy_reports/*/geo_monitor.md`
- `output/strategy_reports/*/geo_monitor_data.json`
- 数据库表：`strategy_reports`，`report_type=geo_monitor`

当前限制：

- 第一版为手动执行，不含后台定时任务。
- 暂未画趋势折线图。
- 暂未做自动通知、邮件、微信推送。

## 新增代码文件

- `geo_app/strategy_workflow.py`
- `docs/GEO功能开发进度.md`

## 修改代码文件

- `app.py`
- `geo_app/qwen_client.py`
- `geo_app/storage.py`
- `requirements.txt`

## 新增数据库表

### strategy_reports

用途：统一保存竞品分析、AI 可见度诊断、品牌策略、手动监控报告。

字段：

- `report_type`：报告类型，包含 `competitor`、`visibility`、`brand_strategy`、`geo_monitor`
- `subject`：主题或监控名称
- `city`
- `industry`
- `customer_product`
- `competitors`
- `report_md`
- `raw_json`
- `file_path`
- `created_at`

## 未完成功能

1. 多 AI 搜索引擎支持：DeepSeek、豆包、Gemini、Perplexity、Google AI Overview。
2. 官网深度爬取：站点地图、服务页、案例页、FAQ、Schema、联系方式、资质页。
3. PDF OCR：扫描版 PDF 和图片资料的文字识别。
4. 品牌知识库实体管理：品牌介绍、卖点、证据、案例、FAQ 的结构化维护。
5. 策略报告与文章生成联动：把品牌策略、竞品差距、AI 可见度问题自动注入文章提示词。
6. 自动监控任务：定时执行、失败重试、周期汇总。
7. 趋势图表和可视化：关键词热度曲线、提及率曲线、竞品占比图。
8. PDF/PPT 报告导出。
9. 权限与账号体系。
10. 成本统计：SerpApi、Qwen、媒介发布费用的单任务成本核算。

## 后续建议开发顺序

1. 把“品牌定位策略报告”沉淀成结构化品牌知识库。
2. 文章生成时读取品牌知识库、竞品差距、AI 可见度问题。
3. 增加官网深度分析和结构化信源建议。
4. 增加多 AI 搜索引擎适配层。
5. 增加自动监控与月报汇总。
6. 增加 PDF/PPT 售前报告导出。

## 使用注意

1. `.env` 中需要配置 `DASHSCOPE_API_KEY` 和 `SERPAPI_API_KEY`。
2. PDF 路径必须是本机可访问路径。
3. 第一版报告以 Markdown 为准。
4. 资料不足不会中断生成，但报告会标记待补充内容。
5. 手动监控每执行一次都会保存一份新报告，后续可用于历史对比。

## 2026-07-01 模拟测试记录

测试场景：

- 城市/市场：Los Angeles
- 行业：LED Sign Company
- 客户/品牌：BrightLA Signs
- 核心词：custom LED signs Los Angeles
- 竞品：Front Signs、Signs.com

已执行模块：

1. 竞品分析：成功。
   - 输出：`output/strategy_reports/20260701T065007_d4d41e_custom_LED_signs_Los_Angeles/competitor_analysis.md`
   - 结果：报告识别 BrightLA Signs 在公开搜索中实体认知较弱，Front Signs、Signs.com、SignMakers 等竞品/同行具备更强信源。

2. AI 可见度诊断：成功。
   - 输出：`output/strategy_reports/20260701T065212_9247f6_custom_LED_signs_Los_Angeles/ai_visibility.md`
   - 结果：报告能统计品牌提及、竞品出现、情绪和引用来源。

3. 品牌定位策略：成功。
   - 输出：`output/strategy_reports/20260701T065421_231332_custom_LED_signs_Los_Angeles/brand_strategy.md`
   - 结果：报告给出 BrightLA Signs 应聚焦 “Los Angeles local permit + installation + turnkey signage” 的定位方向。

4. GEO 手动监控：成功。
   - 输出：`output/strategy_reports/20260701T065643_00f557_BrightLA_Signs_LA_LED_Sign_Monitor_Test/geo_monitor.md`
   - 结果：报告生成本次手动监控结论，记录客户提及率、竞品动态、内容缺口和下一轮动作。

测试中发现并已修复：

1. 英文测试问题超过 200 字符时被过滤，导致实际执行问题数少于用户输入值。
   - 修复：问题最大长度从 200 提升到 320。
   - 文件：`geo_app/strategy_workflow.py`

2. 品牌策略搜索词可能出现城市重复，例如 `custom LED signs Los Angeles Los Angeles`。
   - 修复：新增 `_append_city_once()`，如果核心词已包含城市则不重复追加。
   - 文件：`geo_app/strategy_workflow.py`

仍需后续优化：

1. 如果 AI 生成的问题数仍不足用户设定，应自动生成 fallback 问题补齐。
2. AI 可见度统计目前依赖模型返回 JSON，需要增加更严格的解析校验。
3. 报告生成耗时较长，后续可增加后台任务队列、进度日志和取消按钮。
4. Console 在 Windows PowerShell 下显示中文进度会乱码，但保存的 Markdown 文件为 UTF-8，内容正常。
