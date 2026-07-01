# GEO 文章生成与媒介库发布

第一版是本地 Streamlit 工具，用于创建 GEO 推广任务、用 Qwen 搜索/分析/写作，并在人工确认后调用媒介库发布。

## 运行

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

建议复制 `.env.example` 为 `.env`，并填写：

- `DASHSCOPE_API_KEY`
- `MEIJIEKU_MOBILE`
- `MEIJIEKU_PASSWORD`

## 流程

1. 新建任务：输入推广词条和客户产品。
2. Qwen 联网搜索：默认搜索 3 次，每次取前 10 条链接。
3. Qwen 链接分析：生成 `文章生成格式.md`。
4. 媒介库匹配：网站媒体和自媒体都查，名称/域名先完全匹配，再模糊匹配。
5. 人工确认：模糊匹配必须确认，发布前必须勾选扣费确认。
6. 文章生成：每个平台即时生成一篇不同文章，客户产品排第一。
7. 发布和状态查询：保存订单号，下次启动可继续同步未完成订单。

## 数据目录

```text
output/
  geo_tasks.sqlite3
  tasks/
    任务ID_推广词条/
      文章生成格式.md
      search_results.json
      platform_matches.json
      articles/
```

## 安全提醒

原脚本中曾硬编码 Qwen API Key。请在阿里云百炼后台重置旧 Key，并改用 `.env` 或界面输入。

## 媒介库接口说明

媒介库当前 API 地址应配置为：

```text
https://api.meijieku.com
```

注意：接口路径不带 `/api` 前缀，例如登录接口是：

```text
POST https://api.meijieku.com/System/login_long_token
```

在真实媒介库接口确认前，可以在左侧开启“媒介库模拟模式（不请求真实接口）”，用于测试平台匹配、文章生成和发布前确认流程。
