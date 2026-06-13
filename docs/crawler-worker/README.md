# 悦享资源库 crawler-worker 说明

更新时间：2026-06-14

## 1. 这个 worker 是什么

`crawler-worker` 是独立的采集服务，专门处理需要浏览器或外部站点访问的资源采集任务。

它和主后端分开运行：

- 主后端：负责小程序、后台、积分、解锁、反馈、导入、审核等核心接口。
- crawler-worker：负责 KDocs、LinuxDo 等外部资源采集和定时同步。

这样做的目的：

- 主后端不再安装 Chromium，部署更轻。
- 爬虫异常不会拖垮小程序和后台主接口。
- 后续其他项目也可以复用这个 worker 思路。
- 服务器访问不了某些站点时，可以改用 PC 导出文件、后台导入的方式。

## 2. 当前部署状态

服务器 Docker 里目前是单独容器：

| 服务 | 容器名 | 作用 |
|---|---|---|
| 主后端 | `video-service-app` | 小程序和 PC 后台接口 |
| 爬虫 worker | `video-service-crawler-worker` | KDocs / LinuxDo 采集 |

当前 worker 健康检查：

```bash
docker compose exec -T crawler-worker curl -fsS http://localhost:8010/health
```

正常返回示例：

```json
{"status":"ok","service":"crawler-worker","chromium":"/usr/bin/chromium"}
```

## 3. 当前采集任务

| key | 来源 | 规则 | 说明 |
|---|---|---|---|
| `kdocs_anime` | KDocs 影视剧 | 每 60 分钟 | 只取最新日期分组，最多 20 条 |
| `kdocs_movie` | KDocs 电影 | 每天 00:00 | 只取最新日期分组，最多 20 条 |
| `kdocs_4k` | KDocs 4K影视 | 每天 00:00 | 只取最新日期分组，最多 20 条 |
| `linuxdo` | LinuxDo | 每 12 小时 | 默认最新 20 条，高置信入库，低置信进待审核 |

KDocs 如果能识别日期，就按最新日期分组处理；如果文档不是严格倒序，也不会简单拿前 20 条。

## 4. 后台如何触发

PC 后台点击采集按钮时，实际流程是：

```text
PC 后台
  -> 主后端 /admin/netdisk/crawlers/{key}/run
  -> crawler-worker /run/{key}
  -> 去重 / 分类 / 入库或进入待审核池
```

主后端只是转发，不直接跑浏览器采集。

## 5. 为什么不立刻拆成独立 Git 仓库

当前建议先不拆仓库，原因：

- 现在还在 MVP 快速迭代期，接口、模型、去重规则还会继续调整。
- worker 仍复用主项目里的数据库模型、分类服务、入库服务。
- 先放在同仓库更方便一次部署、一套迁移、一套回归。

建议拆仓条件：

- worker 稳定运行 1 周以上。
- 采集来源超过 4 个，并且开始服务多个项目。
- 入库接口稳定，不再直接依赖主项目内部模型。
- 需要单独发布 worker 镜像或单独扩容。

## 6. 相关文档

- [采集规则说明](./采集规则说明.md)
- [PC导入与服务器入库流程](./PC导入与服务器入库流程.md)
- [故障处理](./故障处理.md)
- [后续拆仓建议](./后续拆仓建议.md)

