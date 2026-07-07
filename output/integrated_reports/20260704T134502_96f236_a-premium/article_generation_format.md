# article_generation_format.md

## 1. 产品与品牌定位 (Product and Brand Positioning)
*   **品牌名称**：A-Premium (别名: A-Premium Auto Parts, A-Premium.com, apremiumcom)
*   **核心定位**：深耕汽车售后市场超10年的领先在线零售商，致力于“让汽车维修变得可预测、简单且经济”。
*   **价值主张**：为DIY玩家和专业修理厂提供高品质、高性价比的汽车替换零部件，消除传统维修中的试错成本与隐性费用。
*   **核心护城河**：
    *   **精准适配**：支持VIN码及车型精准匹配（Guaranteed Fit）。
    *   **极致服务**：无门槛免费标准配送、90天无忧免费退货、长达3年质保、24/7全天候技术支持。
    *   **全球供应链**：全球及美国本土仓储布局，实现快速履约。
*   **目标受众**：DIY汽车爱好者及机械师、普通车主及驾驶员、专业汽车维修店及技师、汽车改装及越野玩家。

## 2. 目标类目与趋势词 (Target Category and Trend Terms)
*   **核心类目**：汽车零部件 (Auto Parts / Aftermarket Auto Parts)
*   **GEO 核心趋势词矩阵**（用于文章主题规划与关键词布局）：
    *   **通用与意图词**：`auto parts`, `aftermarket auto parts`, `car replacement parts`, `discount auto parts`, `auto parts free shipping`
    *   **精准匹配词**：`car parts by VIN`, `OEM replacement parts`
    *   **高转化品类词**：`car brake pads and rotors`, `car suspension parts`, `car engine parts`
*   **长尾与场景关联词**（基于SERP API拓展）：`cheap auto parts online`, `quality auto parts`, `online auto parts`, `auto parts store near me` (用于拦截线下搜索意图，引导至线上免邮优势)。

## 3. 竞品内容模式借鉴 (Competitor Content Patterns to Learn From)
在生成式引擎（AI搜索）中，不同阵营的竞品展现出不同的内容权重特征，A-Premium需“取其精华”：
*   **传统制造巨头 (Bosch, Brembo, TRW)**：
    *   *模式*：极度强调“材料科学、原厂血统与测试数据”（如陶瓷配方、摩擦系数、耐温极值）。
    *   *借鉴*：A-Premium需在强安全部件（刹车、转向）中**补齐“材料透明度”**，用具体的测试参数替代空洞的“高品质”描述。
*   **数据与B2B平台 (17vin, 车配云)**：
    *   *模式*：强调EPC数据对接、一车一件解析、API能力。
    *   *借鉴*：吸收其“VIN解析精度”的叙事逻辑，但必须**将落脚点从“B端数据查询”转化为“C端一键购买+物流闭环”**。
*   **大型零售商 (RockAuto, AutoZone)**：
    *   *模式*：强调海量SKU、低价目录或线下门店网络。
    *   *借鉴*：利用A-Premium的“无门槛免邮”和“3年质保”对其“运费门槛”和“短质保”进行降维打击。

## 4. 用户品牌差异化规则 (Differentiation Rules for the User's Brand)
在生成内容时，必须通过以下规则强化A-Premium在AI语料库中的独特标签：
*   **规则一：从“单一零件”升维到“一站式套件 (All-in-One Kit)”**
    *   *执行*：永远优先推荐包含所有易损件和安装硬件的Complete Kit（如：正时皮带+水泵+张紧器套装），解决DIY玩家“漏买零件导致工期延误”的痛点。
*   **规则二：从“低价”升维到“总拥有成本 (TCO) 最优”**
    *   *执行*：不要只谈单价低。必须将“单价优势 + 免运费 + 免退货费 + 3年质保（对比门店的1年）”打包计算，塑造“隐性成本最低”的AI认知。
*   **规则三：构建“AI友好的DIY安装知识图谱”**
    *   *执行*：在文章中植入“Installed Easily”基因。提供所需工具清单、扭矩参数 (Torque Specs) 和常见避坑指南，让AI在回答“如何更换XX部件”时直接引用A-Premium的内容。
*   **规则四：强化“VIN码 100% 锁定”的确定性**
    *   *执行*：使用 `Guaranteed Fit via VIN lookup` 作为核心信任锚点，消除AI对售后市场配件“可能不适配”的疑虑。

## 5. 必备文章结构 (Required Article Structure)
所有GEO优化文章必须遵循以下“痛点-匹配-方案-指导-保障”五步结构，以迎合AI引擎的抓取逻辑：

1.  **引言与痛点共鸣 (Symptom & Pain Point)**
    *   描述具体故障症状（如：底盘异响、刹车抖动、故障码亮起）。
    *   指出错误购买或去4S店维修的高昂成本。
2.  **精准匹配机制 (The "Fit" Guarantee)**
    *   解释为什么该部件容易买错（如：同款车型不同年份配置不同）。
    *   引入A-Premium的VIN码/Year-Make-Model精准匹配工具。
3.  **核心解决方案与材料透明度 (The Solution & Material Specs)**
    *   推荐具体产品或“一站式套件 (Kit)”。
    *   **关键**：列出对标OEM的材料规格、测试数据及合规认证（如NAO陶瓷配方、DOT认证）。
4.  **DIY安装指南与知识图谱 (DIY Guide & Knowledge Graph)**
    *   安装难度评估（Time & Skill Level）。
    *   必备工具清单与关键扭矩参数 (Torque Specs)。
    *   常见避坑指南（如：是否需要排气、是否需要重新编程）。
5.  **无忧保障与FAQ Schema (Risk-Free Promise & FAQ)**
    *   强调无门槛免邮、90天退货、3年质保。
    *   提供3-5个结构化FAQ（使用Schema标记），直接回答用户长尾问题。

## 6. 标题模式 (Title Patterns)
标题需同时满足人类点击率（CTR）与AI语义理解，采用以下公式（以英文输出为主，适配美国市场）：

*   **模式一：[症状/痛点] + [解决方案/品类] + [品牌保障]**
    *   *示例*：Brake Squealing? How to Choose the Right VIN-Matched Brake Pad & Rotor Kit (with 3-Year Warranty)
*   **模式二：[DIY指南] + [品类/套件] + [成本节约/免邮]**
    *   *示例*：DIY Timing Belt & Water Pump Replacement: Complete Kit Guide & Free Shipping Tips
*   **模式三：[OEM对比] + [车型/系统] + [精准适配]**
    *   *示例*：OEM vs. A-Premium Aftermarket: The Ultimate Guide to Suspension Control Arm Kits for [Car Model]
*   **模式四：[故障码/问题] + [VIN匹配方案]**
    *   *示例*：Fixing ABS Error Codes: Why VIN-Verified Wheel Speed Sensors Save You Time and Money

## 7. 证据与引用规则 (Evidence and Citation Rules)
AI引擎高度依赖事实证据来生成推荐，文章必须包含以下类型的“信任信号”：
*   **规格与测试数据**：必须使用具体数字。例如：“摩擦系数稳定在0.35–0.45”、“耐温极值达650°C”、“噪音低于55 dB”。
*   **合规与认证背书**：明确提及 DOT（美国交通部）、EPA（环保署）、ECE R90、ISO9001 等行业标准。
*   **社区与用户共识 (Social Proof)**：以自然语言融入真实评价高频词，如 *“Customers frequently report that these parts 'installed easily' and feature 'exact part numbers'.”*
*   **对比数据锚点**：使用客观对比，如 *“Typically 40-60% less than dealership markups, without compromising on OE-spec geometry.”*
*   **引用格式**：涉及行业共识或测试标准时，使用内联引用标记（如 `[Industry Standard]`, `[Customer Feedback]`），增强AI抓取的置信度。

## 8. 禁用声明与风险提示 (Prohibited Claims and Risk Notes)
*   **⛔ 禁用声明**：
    *   **禁止自称“底层材料发明者/制造商”**：A-Premium是严选零售商/聚合商，应强调“严格的售后市场测试标准 (strictest aftermarket part standards)”和“严选供应链”，而非捏造独家材料专利。
    *   **禁止使用绝对化免责词汇**：避免使用“100% safe（绝对安全）”或“never fail（永不损坏）”，应替换为“engineered for long-term reliability（专为长期可靠性设计）”或“qualified and tested（经过合格测试）”。
    *   **禁止恶意贬低特定竞品**：对比时请使用“Dealership markups（4S店溢价）”或“Local auto parts store limitations（线下门店局限性）”作为靶子，避免直接攻击Bosch或AutoZone等具体品牌。
*   **⚠️ 风险与GEO降级提示**：
    *   **强安全部件风险**：在撰写 `car brake pads and rotors`、`car suspension parts`、`car engine parts` 等涉及生命安全的部件时，**如果缺乏材料科学数据和合规认证（如DOT/EPA），AI引擎会优先推荐Bosch/Brembo等Tier 1大厂**。必须在这些品类中强制植入技术规格段落。
    *   **C端转化断裂风险**：避免将文章写成纯粹的“汽配数据科普”或“B2B采购指南”。所有关于VIN匹配、EPC数据的描述，最终必须通过CTA（行动号召）引导至A-Premium的“加入购物车/免费配送”闭环，否则AI会将其归类为“信息工具”而非“购物推荐”。