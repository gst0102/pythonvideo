# KDocs 预览与头像 / 每日积分 Codex 自测报告

## 1. 本次修改目标

- KDocs 同步资源先生成重复 / 脏数据安全清理预览，不直接删、不直接隐藏。
- 修复微信小程序登录后头像仍显示默认头像的问题。
- 确认“每日获取积分 0/60”的分子是否动态。

## 2. 修改文件列表

- `scripts/preview_kdocs_dirty_resources.py`
- `scripts/cleanup_kdocs_same_link_duplicates.py`
- `docs/qa/KDocs重复脏数据_清理预览报告.md`
- `src/api/request.ts`
- `src/pages/user-login/login.vue`
- `src/store/index.ts`

## 3. 核心实现说明

- 新增 KDocs 只读预览脚本，统计同链接重复、同 source_ref 重复、同名同盘重复、空链接、缺 source_ref 等脏数据类型。
- 新增 KDocs 同链接重复安全隐藏脚本，默认 dry-run，必须显式 `--execute` 才会隐藏；保留有 source_ref 且最新的一条。
- 执行脚本保护有下载、收藏、投诉、积分流水、补链关联的资源，不自动隐藏。
- 头像上传接口现在会校验后端返回 code 和 upload_image；上传失败不会再返回空值。
- 登录页不再把 `wxfile://`、`file://` 等临时路径当作头像保存，避免重启后头像失效回默认图。
- 用户资产接口返回头像 / 昵称时，会同步更新本地 `userInfo` 缓存。
- 每日积分显示已确认由 `mine/assets` 动态字段计算：`netdisk_stats.today_earned_points`、`points_wallet.today_earned_points`、`today_can_earn`。

## 4. 已运行测试

- `python3 -m py_compile myproject/scripts/preview_kdocs_dirty_resources.py`
- `python3 -m py_compile myproject/scripts/cleanup_kdocs_same_link_duplicates.py`
- `npm run build:mp-weixin`
- 生产后端容器只读执行：`python3 /app/scripts/preview_kdocs_dirty_resources.py`
- 生产后端容器 dry-run 执行：`python3 /app/scripts/cleanup_kdocs_same_link_duplicates.py --limit 14`

## 5. 测试结果

- 小程序构建通过。
- KDocs 预览脚本语法检查通过。
- 生产只读预览成功输出报告，没有执行删除、隐藏或更新。
- 同链接重复 dry-run 结果：57 组重复链接，56 条可安全隐藏，1 条因关联数据进入人工复核。

## 6. 未覆盖测试项

- 尚未在微信开发者工具里实机重新登录验证头像展示。
- 尚未用指定用户 token 调 `/mine/assets` 对账当天积分流水。

## 7. 可能影响范围

- 登录页头像上传失败时，用户会看到错误提示，需要重新选择头像；这是为了避免保存脏头像路径。
- KDocs 脚本目前只是预览工具，不改变线上数据。
- KDocs 同链接重复隐藏脚本已部署到生产容器，但本次没有传 `--execute`，没有改变线上数据。

## 8. 需要人工确认

- 是否同意下一步对 56 条“同链接重复活跃资源”执行隐藏。
- 如果某个具体用户今天已经赚过积分但仍显示 `0/60`，需要提供该账号或让我查该用户当天积分流水。
