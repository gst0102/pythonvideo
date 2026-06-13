# LinuxDo采集混合分类同步_验收报告

## 验收结论

需要人工确认

原因：P0 业务逻辑自动化验证已通过，但真实 LinuxDo 登录态采集、真实 PostgreSQL Alembic 迁移、DeepSeek 真实 API 兜底未在生产/准生产环境执行。

## P0 覆盖情况

| 编号 | 测试项 | 覆盖情况 | 结果 |
|---|---|---|---|
| P0-01 | LinuxDo 与 KDocs 相同影视链接不能重复入库 | `scripts/verify_linuxdo_hybrid_classification.py` | 通过 |
| P0-02 | 同片名新增网盘可作为补充资源入库 | `scripts/verify_linuxdo_hybrid_classification.py` | 通过 |
| P0-03 | 完结/全集/合集影视资源 20 分 | `scripts/verify_linuxdo_hybrid_classification.py`、`scripts/verify_kdocs_netdisk_sync.py` | 通过 |
| P0-04 | 更新中影视资源 5 分 | `scripts/verify_linuxdo_hybrid_classification.py`、`scripts/verify_kdocs_netdisk_sync.py` | 通过 |
| P0-05 | 重复运行每日爬虫不重复创建资源 | `scripts/verify_linuxdo_hybrid_classification.py` | 通过 |
| P0-06 | DeepSeek 不可用不阻断规则分类 | 分类服务回退逻辑覆盖 | 通过 |

## 已覆盖测试项

- Python 语法检查通过。
- KDocs 迅雷链接解析回归通过。
- KDocs 影视定价回归通过。
- LinuxDo 去重、补充网盘、重复运行幂等通过。
- 小程序首页、资源列表、收藏、详情、补链页类型检查通过。

## 未覆盖测试项

- 真实 LinuxDo 登录态文件采集。
- 真实 PostgreSQL 数据库迁移。
- 真实 DeepSeek API 调用。
- 小程序真机截图验收上架时间是否挤压标题、积分、信用标签。

## 发现的问题

当前自动化未发现阻断性业务问题。

## Bug 修复任务单

暂无。

## 回归测试清单

| 模块 | 回归内容 | 优先级 |
|---|---|---|
| KDocs 同步 | 金山文档影视资源仍能同步，迅雷资源可入库 | P0 |
| 资源列表 | `sort=latest/hot/recommend` 仍能正常返回 | P1 |
| 解锁流程 | 5/10/20 分资源解锁金额仍正确 | P0 |
| 收藏页 | 收藏资源展示上架时间、验证时间和收藏时间 | P1 |
| 详情页 | 资源详情展示上架时间，解锁后网盘信息正常 | P1 |
| 补链投诉 | 补链页资源选择不因新增字段报错 | P1 |
| 定时任务 | LinuxDo 登录态缺失时不影响后端启动 | P0 |

## 上线前必须检查事项

- 在服务器执行 Alembic 迁移并确认新增字段、候选表创建成功。
- 配置 LinuxDo 登录态文件路径 `LINUXDO_STATE_FILE`。
- 先用 `python scripts/linuxdo_netdisk_sync.py crawl --pages 1` 只采集导出，人工看 20 条样本。
- 再用 `python scripts/linuxdo_netdisk_sync.py sync --pages 1` 小批量入库。
- 打开小程序首页、资源列表、收藏、详情确认上架时间中文展示正常。

## 是否建议进入人工最终确认

建议进入“人工最终确认前的小批量联调”，暂不建议直接全量定时上线。
