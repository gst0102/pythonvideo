# KDocs同链接重复资源软隐藏_Codex自测报告

## 1. 本次修改目标

处理 KDocs 同链接重复活跃资源，减少首页、搜索、今日精选被旧脏数据干扰。

## 2. 修改文件列表

- `scripts/cleanup_kdocs_same_link_duplicates.py`
- `scripts/preview_kdocs_dirty_resources.py`
- `docs/qa/KDocs同链接重复资源软隐藏_Codex自测报告.md`

## 3. 核心实现说明

- 本次没有删除数据，只执行软隐藏：`netdisk_resources.is_active = false`。
- 只处理 KDocs 活跃资源中“同链接重复”的安全候选。
- 保留规则：优先保留有 `source_ref` 且 `verified_at / updated_at / created_at` 最新的记录。
- 保护规则：有下载、收藏、投诉、积分流水、补链关联的重复项不自动隐藏。

## 4. 已运行测试

- 生产 dry-run：`python3 /app/scripts/cleanup_kdocs_same_link_duplicates.py --limit 12`
- 生产执行：`python3 /app/scripts/cleanup_kdocs_same_link_duplicates.py --execute --limit 12`
- 生产执行后复查：`python3 /app/scripts/cleanup_kdocs_same_link_duplicates.py --limit 20`
- 今日精选回归：`python3 /app/scripts/verify_featured_today_selection.py`
- 线上接口复查：`GET /netdisk/resources/featured-today?limit=3`

## 5. 测试结果

执行前：

- 同链接重复活跃总行数：114
- 保留行：57
- 可安全隐藏候选：56
- 受保护需人工复核：1
- 重复链接组数：57

执行结果：

- 已软隐藏：56
- 删除记录：0

执行后：

- 同链接重复活跃总行数：2
- 可安全隐藏候选：0
- 受保护需人工复核：1
- 剩余重复组：1

今日精选接口前三条：

- `天赐的声音 第7季.1080P更 6.15期`，显示 `今天 / 刚刚`
- `无限超越班 第四季.1080P更6.15期`，显示 `今天 / 刚刚`
- `喜欢你我也是 第六季.1080P更 6.15期`，显示 `今天 / 刚刚`

## 6. 未覆盖测试项

- 剩余 1 组重复资源包含下载/收藏行为，未自动隐藏，需要人工复核。
- 同名同盘但不同链接的重复资源未自动处理，避免误伤不同集数或不同清晰度。

## 7. 可能影响范围

- 资源列表、搜索、今日精选会少展示同链接旧重复资源。
- 已有用户行为关联的资源未自动处理，不影响用户获取历史和收藏。

## 8. 需要人工确认

剩余受保护重复项：

- `灵魂摆渡·十年.1080P更 24【超前完结】`
- 网盘：迅雷
- 原因：两条记录都有下载/收藏关联，不自动隐藏。
