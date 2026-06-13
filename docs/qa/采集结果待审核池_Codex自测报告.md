# 采集结果待审核池 Codex 自测报告

## 1. 本次修改目标

- 后台新增采集结果待审核池。
- LinuxDo 低置信、疑似重复、新增网盘补充资源可单独筛选。
- 运营可对候选执行通过、跳过、合并。

## 2. 修改文件列表

- `controllers/admin.py`
- `services/netdisk_resource_service.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/router/index.ts`
- `adminVideo/src/layout/index.vue`
- `adminVideo/src/store/index.ts`
- `adminVideo/src/views/netdisk/ops-center.vue`
- `adminVideo/src/views/netdisk/collected-resources.vue`
- `docs/qa/采集结果待审核池_测试清单与验收标准.md`
- `scripts/verify_collected_resource_review_pool.py`

## 3. 核心实现说明

- 新增 `GET /admin/netdisk/collected-resources`：
  - 支持 `bucket=all/low_confidence/duplicate/supplement`。
  - 支持 `status=pending/published/merged/skipped/all`。
  - 支持关键词搜索和分页。
- 新增 `POST /admin/netdisk/collected-resources/{id}/{action}`：
  - `approve`：发布为正式资源。
  - `skip`：跳过，不入库。
  - `merge`：新增网盘补充可入库；同链接重复不会重复创建资源。
- PC 后台新增“采集待审核池”页面。
- 待处理中心采集任务面板增加“进入待审核池”入口。
- 侧边栏新增“采集待审核池”，待处理小红点总数纳入 pending 采集候选。

## 4. 已运行测试

- 后端静态检查：
  - `python3 -m py_compile controllers/admin.py services/netdisk_resource_service.py`
- PC 后台类型检查：
  - `vue-tsc --noEmit`
- PC 后台生产构建：
  - `vite build`
- 采集候选处理联调：
  - `PYTHONPATH=/tmp/yuexiang_pydeps:/Users/yiyi/Desktop/Desktop/vedo-project/myproject python scripts/verify_collected_resource_review_pool.py`

## 5. 测试结果

- 后端静态检查通过。
- PC 后台类型检查通过。
- PC 后台构建通过。
- Vite 仍有既有大包提示，不影响本次功能。
- 采集候选处理联调通过：
  - 低置信候选 `approve` 后创建正式资源，候选状态为 `published`。
  - 同链接候选 `merge` 后不重复创建正式资源，候选状态为 `merged`。
  - 新增网盘候选 `merge` 后创建补充网盘资源，候选状态为 `merged`。
  - 已处理候选重复点击 `merge` 不会重复创建资源。

## 6. 未覆盖测试项

- 未连接生产/服务器真实数据库调用候选列表接口。
- 本轮使用隔离内存数据库验证业务处理逻辑，未污染本地或生产数据。
- 未验证主管权限以外角色的真实拦截效果。

## 7. 可能影响范围

- LinuxDo 采集候选处理流程。
- 后台待处理总数。
- 资源库正式资源来源为 `linuxdo` 的入库路径。

## 8. 需要 AI 测试官复核的事项

- 同一候选重复点击通过/合并不能重复创建资源。
- 同链接重复候选合并时不创建新资源。
- `supplement_pan` 候选合并后可以作为补充网盘资源入库。
