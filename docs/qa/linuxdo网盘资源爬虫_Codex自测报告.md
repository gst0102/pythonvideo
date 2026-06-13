## 1. 本次修改目标

新增一个独立命令行爬虫目录，用于从 linux.do 网盘资源分类采集帖子标题、爬取时间、帖子时间、网盘类型、网盘链接和访问码。

## 2. 修改文件列表

- `myproject/linuxdo_resource_crawler/linuxdo_resource_crawler.py`
- `myproject/linuxdo_resource_crawler/README.md`
- `myproject/linuxdo_resource_crawler/.gitignore`
- `myproject/linuxdo_resource_crawler/fixtures/sample_topic.json`
- `myproject/linuxdo_resource_crawler/outputs/.gitkeep`
- `myproject/docs/qa/linuxdo网盘资源爬虫_Codex自测报告.md`

## 3. 核心实现说明

- 使用 Discourse JSON 接口采集，不依赖打开浏览器。
- 使用 Python 标准库请求网络，不需要额外安装 `requests`。
- 支持分类批量采集、指定帖子采集、指定 topic id 采集。
- 支持从帖子 URL 文本列表批量采集，便于承接 Google 搜索结果。
- 支持 Netscape 格式 `cookies.txt`，用于用户自行登录态下采集可见内容。
- 支持 Discourse API Key / API Username，适合替代短期 cookie 做长期任务。
- 支持检查 cookie 文件中 linux.do cookie 名称和过期时间，不输出 cookie 值。
- 输出 CSV 和 JSONL，便于后续导入网盘资源库。
- 仅采集公开元数据和链接，不下载网盘内容，不绕过登录或权限。

## 4. 已运行测试

- 本地 fixture 解析测试。
- 帖子 URL 列表读取测试。
- cookie 健康检查逻辑补充。
- 线上 linux.do 分类 JSON 探测。

## 5. 测试结果

- 本地 fixture 可成功提取夸克、百度、金山文档链接，并识别提取码/口令。
- 帖子 URL 列表可正确读取纯 topic id 和完整帖子地址。
- 当前环境直接访问 linux.do JSON 接口返回 Cloudflare 403，使用项目已有 `cookies.txt` 仍返回 403；脚本已设置超时并会输出失败原因。

## 6. 未覆盖测试项

- 未使用真实登录 cookie 进行完整分类采集。
- 未验证导入后台资源库的数据库写入流程。
- 未做大批量采集稳定性测试。

## 7. 可能影响范围

本次只新增独立目录和文档，不修改现有业务代码、数据库模型、接口和前端页面。

## 8. 需要 AI 测试官复核的事项

- 采集资源后进入平台前，仍需人工或审核策略确认链接有效性、版权/合规风险、分类准确性。
- 若后续要自动导入数据库，需要补充去重、审核状态、成本积分、上传者归属和失效投诉策略。
