# 资源上架时间入库口径修复_Codex自测报告

## 1. 本次修改目标

- 修复资源卡“上架时间”误用 KDocs 最近同步时间的问题。
- 上架时间统一使用资源首次进入数据库的 `created_at`。
- `verified_at` 只用于“已验证刚刚/几小时前”展示。
- 首页“今日精选”和资源列表默认排序统一按 `created_at desc`，保证上架时间最新在最前面。

## 2. 修改文件列表

- `myproject/services/netdisk_resource_service.py`
- `docs/codex-error-memory.md`

## 3. 核心实现说明

- `_resource_published_at_value` 改为直接返回 `created_at`。
- `published_at_precise` 继续按北京时间格式化为 `M月D日 HH:mm`。
- 移除今日精选按“最新同步批次”提前返回的逻辑，改为今天新入库资源按入库时间倒序后去重。
- 资源列表默认第一页不再走最新同步批次特殊排序，回到 `created_at desc`。
- 生产容器已做最小热修并重启。

## 4. 已运行测试

- `python3 -m py_compile services/netdisk_resource_service.py schemas/netdisk.py controllers/vip.py`
- 生产 `GET /health`
- 生产 `GET /netdisk/resources/featured-today?limit=3`
- 生产 `GET /netdisk/resources?keyword=飞常日志&page=1&page_size=3`
- 生产 `GET /netdisk/resources/featured-today?limit=5`
- 生产 `GET /netdisk/resources?page=1&page_size=5&sort=latest`

## 5. 测试结果

- 生产健康检查通过。
- 今日精选前三条返回：
  - `天赐的声音 第7季.1080P更 6.15期`：`created_at=2026-06-13T14:55:12+00:00`，`published_at_precise=6月13日 22:55`
  - `无限超越班 第四季.1080P更6.15期`：`created_at=2026-06-14T02:05:15+00:00`，`published_at_precise=6月14日 10:05`
  - `喜欢你我也是 第6季.1080P更 6.15期`：`created_at=2026-06-13T14:55:12+00:00`，`published_at_precise=6月13日 22:55`
- 搜索 `飞常日志` 返回 `published_at_precise=6月15日 22:30`，与其真实入库时间一致。
- 今日精选前五条已按上架时间倒序：
  - `飞常日志 第二季.1080P更 01`：`6月15日 22:30`
  - `爱情有烟火.1080P更 04【新】`：`6月15日 21:30`
  - `吞噬星空.1080P更 228`：`6月15日 20:30`
  - `为爱闪耀的她.1080P更6.15期`：`6月15日 18:48`
  - `奔跑吧 第十季.1080P更 6.15期`：`6月15日 18:31`

## 6. 未覆盖测试项

- 未在微信开发者工具真机截图复核，需要用户重新进入小程序页面确认展示刷新。

## 7. 可能影响范围

- 首页今日精选、资源列表、详情页、收藏页、反馈补链页的资源上架时间展示。

## 8. 需要人工确认

- 小程序页面应显示真实入库时间，不应再显示最近同步时间。
