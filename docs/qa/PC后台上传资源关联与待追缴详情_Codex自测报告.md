# PC 后台上传资源关联与待追缴详情_Codex自测报告

## 1. 本次修改目标

- 上传审核通过后正式写入资源表，并建立 `source_upload_id` 关联。
- 资源确认失效后可以追溯上传者，生成待追缴记录。
- 待追缴详情抽屉展示原资源、上传/补链记录、处罚计算方式。
- 追缴扣除前展示用户当前可用积分、预计扣除、扣后缺口。
- 确认失效时记录用户侧通知，说明为什么进入待追缴。

## 2. 修改文件列表

- `models/netdisk_resource.py`
- `models/netdisk_user_notification.py`
- `models/__init__.py`
- `migrations/versions/016_netdisk_upload_resource_notifications.py`
- `services/netdisk_resource_service.py`
- `controllers/admin.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/views/netdisk/risk.vue`
- `docs/qa/PC后台上传资源关联与待追缴详情_Codex自测报告.md`

## 3. 核心实现说明

- `netdisk_resources` 新增 `source_upload_id`，用于追溯资源来源上传记录。
- 新增 `netdisk_user_notifications`，记录用户侧通知。
- 上传审核通过时创建或更新资源：
  - 资源 ID 规则：`upload-{upload_id前24位无横线}`
  - 默认普通资源，消耗 5 分。
  - 资源带上 `source_upload_id`。
- 资源级确认失效时：
  - 隐藏资源。
  - 若资源有关联上传记录，则将上传记录置为 `invalid_confirmed`。
  - 为上传者生成待追缴记录。
  - 为已通过补链者生成待追缴记录。
  - 写入用户通知记录。
  - 幂等键避免重复生成待追缴。
- 新增 `GET /admin/netdisk/risk-records/{record_id}` 返回待追缴详情。

## 4. 已运行测试

- 后端 Python 语法检查。
- PC 后台 `npm run build`。
- 本地数据库结构补齐：
  - `netdisk_resources.source_upload_id`
  - `netdisk_user_notifications`
- 上传审核通过接口验证。
- 待复核池确认失效接口验证。
- 待追缴详情接口验证。
- PC 风控页详情抽屉浏览器验收。

## 5. 测试结果

- 上传审核通过后返回资源：`upload-1f4d3a272e5a4d4bb59e29bd`，`source_upload_id=1f4d3a27-2e5a-4d4b-b59e-29bd498920e8`。
- 资源确认失效后返回：`risk_records_created=1`，`affected_upload=true`，`affected_repairs=0`。
- 待追缴详情返回：
  - `reason=resource_invalid_pending_penalty`
  - `points_due=10`
  - `collect_preview.will_collect=10`
  - 包含上传记录、资源记录、1 条用户通知。
- PC 风控页详情抽屉可见：
  - 用户可用积分
  - 预计扣除
  - 扣后缺口
  - 关联资源
  - 用户通知记录

## 6. 未覆盖测试项

- 本地历史数据库没有 `alembic_version`，直接 `alembic upgrade head` 会从 001 开始撞已有表；本地验证使用安全 SQL 补齐本轮结构。正式环境应走 Alembic 迁移。
- 未做小程序端用户通知列表展示。
- 未做真实大量上传审核通过后的资源列表压力测试。

## 7. 可能影响范围

- 上传审核通过。
- 资源列表与资源详情。
- 待复核池确认失效。
- 风控/待追缴。
- 用户通知记录。

## 8. 需要 AI 测试官复核的事项

- 上传审核通过创建资源的默认等级和消耗分是否符合运营预期。
- 确认失效时上传者和补链者是否都应进入待追缴。
- 用户侧通知是否需要下一轮接入小程序“我的消息”。
