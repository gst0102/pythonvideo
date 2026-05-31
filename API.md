# 视频下载 & 影视资源 API 接口文档

> 文档版本：v2.0  
> 最后全量更新：2026-05-31  
> 说明：每个接口标注独立的最后更新时间，方便 PC 端对接

---

## 架构说明

```
客户端 → FastAPI → ReverseService（平台识别 → 逆向提取 CDN URL）
                         ↓
                  fetch_stream(stream=True)
                         ↓
               CDN 源站 → 边下边传 → 客户端（不落盘）
```

所有平台均采用流式传输，视频数据直接从 CDN 转发给客户端，不写入服务器磁盘。

---

## 支持平台

| 平台 | 提取方式 | 流式 | 封面图 |
|---|---|---|---|
| 抖音 `douyin.com` / `v.douyin.com` | 短链解析 → API 直调 → Playwright 浏览器渲染 + API 拦截 | ✅ | ✅ |
| 头条 `toutiao.com` | yt-dlp 通用提取器 | ✅ | ✅ |
| 小红书 `xhslink.com` / `xiaohongshu.com` | 纯 Python，跟随短链重定向 → 解析 SSR `__INITIAL_STATE__` → 绕过 API 签名 | ✅ | ✅ |
| B站 `bilibili.com` / `b23.tv` | 纯 Python，调用 B站公开 API（view + playurl） | ✅ | ✅ |
| 快手 `kuaishou.com` | Playwright 浏览器渲染 → 提取 video 标签 | ✅ | ✅ |
| 其他（YouTube、微博等） | yt-dlp 通用提取器（兜底） | ✅ | ❌ |

---

## 平台逆向原理速查

| 平台 | 方法 | 关键点 |
|---|---|---|
| 小红书 | 纯 Python SSR | 跟随 `xhslink.com` 302 重定向 → 获取 `acw_tc` cookie → 解析页面 `__INITIAL_STATE__` JSON → 提取 `note.video.media.stream` 多码率视频流 |
| B站 | 纯 API | `/x/web-interface/view` 获取标题+封面+CID → `/x/player/playurl?fnval=1` 获取传统 MP4（非 DASH） |
| 抖音 | 短链→API→Playwright | ① `v.douyin.com` 302 提取 video_id → ② `/aweme/v1/web/aweme/detail/` API 直调 → ③ Playwright 浏览器渲染 + API 拦截 + RENDER_DATA/SSR_HYDRATION 提取 |
| 头条 | yt-dlp | yt-dlp 通用提取器（兼容性最好，无需浏览器），返回真实标题 + 封面图 |
| 快手 | Playwright | Playwright 浏览器渲染 → `video` 标签 `src` + `poster`，返回真实标题 + 封面图 |

---

## 接口列表

---

### 接口 1：获取视频信息

> **最后更新：2026-05-31**（修复头条/抖音/快手返回真实标题和封面图）

```
POST /video/video_info
Content-Type: application/json
```

**说明**：获取视频的标题、封面图、可用下载格式。所有平台均返回真实标题和封面图。

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `url` | string | ✅ | — | 视频链接（支持抖音/头条/小红书/B站/快手短链） |
| `user_id` | string | ✅ | — | 用户标识，用于频率限制 |
| `format_preset` | string | ❌ | `fast` | `fast` 快速 / `medium` 标准 / `quality` 高清 |

**请求示例：**
```json
{
    "url": "https://v.douyin.com/_fc7hMm0NQ8/",
    "user_id": "user_001",
    "format_preset": "fast"
}
```

**成功响应 (200)：**
```json
{
    "code": 200,
    "msg": "获取视频信息成功",
    "data": {
        "title": "制作奶茶中 #奶茶 #同城诸暨 #热门",
        "thumbnail": "https://p3-pc-sign.douyinpic.com/xxx.jpeg",
        "cover_url": "https://p3-pc-sign.douyinpic.com/xxx.jpeg",
        "formats": [
            {
                "preset": "fast",
                "label": "快速",
                "description": "优先MP4格式"
            },
            {
                "preset": "quality",
                "label": "高清",
                "description": "最高质量"
            }
        ]
    }
}
```

**字段说明：**

| 字段 | 说明 |
|---|---|
| `title` | 视频真实标题（不再返回"头条视频"/"抖音视频"等占位符） |
| `thumbnail` | 封面图 URL（同 cover_url，用于前端 img 标签展示） |
| `cover_url` | 封面图 URL |
| `formats` | 可用的下载格式列表 |

**错误响应：**

| 状态码 | `code` | 说明 |
|---|---|---|
| 400 | 400 | 参数错误（URL 无效或缺失） |
| 429 | 429 | 请求频率过高（每用户每IP 5次/分钟） |
| 500 | 500 | 服务器内部异常 |
| 502 | 502 | 网络请求失败 |

---

### 接口 2：下载视频（流式传输）

> **最后更新：2026-05-29**

```
GET /video/user_video?user_id={用户ID}&url={视频URL}&format_preset={预设}
```

**说明**：流式下载视频，数据从 CDN 直传客户端，不落服务器磁盘。

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `user_id` | string | ✅ | — | 用户标识 |
| `url` | string | ✅ | — | **必须 URL 编码** `encodeURIComponent()` |
| `format_preset` | string | ❌ | `fast` | `fast` / `medium` / `quality` |

**⚠️ 重要：`url` 参数必须 URL 编码**

抖音链接 `https://www.douyin.com/jingxuan?modal_id=7637891910186634559` 含有 `?` 和 `=`，不编码会被当作独立查询参数，导致 `url` 被截断为 `https://www.douyin.com/jingxuan`（丢失 `modal_id`）。

```js
// ✅ 正确做法
const encodedUrl = encodeURIComponent("https://www.douyin.com/jingxuan?modal_id=7637891910186634559")
const downloadUrl = `/video/user_video?user_id=xxx&url=${encodedUrl}`

// ❌ 错误做法
const downloadUrl = `/video/user_video?user_id=xxx&url=https://www.douyin.com/jingxuan?modal_id=7637891910186634559`
// 后端实际收到的 url = "https://www.douyin.com/jingxuan"（被截断了！）
```

**成功响应：** 直接返回视频二进制流

| 响应头 | 说明 |
|---|---|
| `Content-Type` | `video/mp4` |
| `Content-Disposition` | `attachment; filename*=UTF-8''{标题}.mp4` |
| `Content-Length` | 文件字节数（CDN 提供时才有） |
| `Accept-Ranges` | `bytes`（支持断点续传 / Range 请求） |

**前端下载示例：**
```html
<!-- 方式一：<a> 标签直接下载 -->
<a :href="`/video/user_video?user_id=${uid}&url=${encodeURIComponent(url)}`" download>
  下载视频
</a>

<!-- 方式二：JS 触发下载 -->
<script>
function downloadVideo(url, uid) {
    const a = document.createElement('a')
    a.href = `/video/user_video?user_id=${uid}&url=${encodeURIComponent(url)}`
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
}
</script>

<!-- 方式三：fetch + Blob（可显示进度） -->
<script>
async function downloadWithProgress(url, uid) {
    const resp = await fetch(`/video/user_video?user_id=${uid}&url=${encodeURIComponent(url)}`)
    const reader = resp.body.getReader()
    const contentLength = +resp.headers.get('Content-Length')
    let received = 0
    const chunks = []
    while (true) {
        const { done, value } = await reader.read()
        if (done) break
        chunks.push(value)
        received += value.length
        console.log(`进度: ${(received / contentLength * 100).toFixed(1)}%`)
    }
    const blob = new Blob(chunks, { type: 'video/mp4' })
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = decodeURIComponent(
        resp.headers.get('Content-Disposition')?.match(/filename\*?=(?:UTF-8'')?(.+)/)?.[1] || 'video.mp4'
    )
    a.click()
    URL.revokeObjectURL(blobUrl)
}
</script>
```

**错误响应：** 同接口1

---

### 接口 3：带进度的视频下载（SSE 流式）

> **最后更新：2026-05-29**

```
POST /video/video_download_with_progress
Content-Type: application/json
```

**说明**：先提取视频信息，再通过 SSE 推送进度，最后返回下载链接。

请求体同接口1。

**响应：** `Content-Type: application/x-ndjson`

逐行推送 JSON，每行一个事件：

```json
{"status":"start","download_id":"abc123","message":"开始处理视频"}
{"status":"processing","progress":30,"message":"视频处理完成，用时0.5秒"}
{"status":"preparing","progress":50,"message":"准备下载...50%"}
{"status":"completed","progress":100,"message":"生成完毕，这是下载链接","download_url":"/video/user_video?url=...","video_title":"制作奶茶中..."}
```

**状态说明：**

| status | 说明 |
|---|---|
| `start` | 开始处理 |
| `processing` | 视频提取中 |
| `preparing` | 准备流式传输 |
| `completed` | 提取完成，`download_url` 可用 |
| `error` | 处理失败，`message` 包含错误信息 |

**前端监听示例：**
```js
async function downloadWithProgress(videoUrl, userId) {
    const resp = await fetch('/video/video_download_with_progress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: videoUrl, user_id: userId }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
            if (!line.trim()) continue
            const event = JSON.parse(line)
            console.log(`[${event.status}] ${event.progress || 0}% ${event.message}`)

            if (event.status === 'completed') {
                const a = document.createElement('a')
                a.href = event.download_url
                a.download = ''
                a.click()
            }
        }
    }
}
```

---

### 接口 4：获取影视资源列表

> **最后更新：2026-05-31**（新增 `4k_url` 字段 + 夸克URL去重逻辑）

```
GET /anime/resources?type=movie&keyword=&page=1&page_size=100
```

**说明**：获取番剧/电影/4K影视资源列表，数据来源于金山文档逆向爬取。

**查询参数：**

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `type` | ❌ | `movie` | `anime` 番剧 / `movie` 电影 / `4k` 4K影视 |
| `keyword` | ❌ | — | 模糊搜索标题 |
| `page` | ❌ | `1` | 页码，从 1 开始 |
| `page_size` | ❌ | `100` | 每页数量 |

**响应：**
```json
{
    "code": 0,
    "message": "SUCCESS",
    "data": {
        "total": 150,
        "list": [
            {
                "anime_id": "anime_0_12345",
                "title": "咒术回战 第二季 更至36集",
                "quality": "1080P",
                "episode": "更至36集",
                "status": "更新中",
                "baidu_url": "https://pan.baidu.com/s/xxx",
                "baidu_password": "ab12",
                "quark_url": "https://pan.quark.cn/s/xxx",
                "4k_url": "https://pan.baidu.com/s/yyy",
                "update_time": "05月31日 14:30"
            }
        ]
    }
}
```

**响应字段说明：**

| 字段 | 说明 | PC端展示建议 |
|---|---|---|
| `anime_id` | 外部数据源唯一 ID | 用于订阅/收藏 |
| `title` | 剧名（含集数信息） | 主标题 |
| `quality` | 画质：1080P / 4K / 720P | 标签/徽章 |
| `episode` | 更新进度（如"更至36集"） | 副标题 |
| `status` | 状态：更新中 / 完结 / 预告 | 状态标签 |
| `baidu_url` | 百度网盘链接 | 复制按钮 |
| `baidu_password` | 百度提取码 | 复制按钮 |
| `quark_url` | 夸克网盘链接 | 复制按钮 |
| `4k_url` | 4K网盘链接 | 复制按钮 |
| `update_time` | 最后更新时间 | 时间显示 |

---

### 接口 5：手动触发金山文档同步

> **最后更新：2026-05-31**（同步频率：番剧15分钟，电影/4K凌晨00:00）

```
GET /admin/sync-anime?type=anime,movie,4k
```

**说明**：手动触发金山文档数据同步。一般不需要手动调用，系统会自动定时同步。

**查询参数：**

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `type` | ❌ | `anime` | 逗号分隔：`anime` / `movie` / `4k` |

**响应：**
```json
{
    "code": 0,
    "message": "同步完成",
    "data": {
        "synced": 150,
        "inactive": 3,
        "error": null
    }
}
```

| 字段 | 说明 |
|---|---|
| `synced` | 本次同步插入/更新的记录数 |
| `inactive` | 本次标记为失效的记录数（金山文档中已删除的） |
| `error` | 错误信息，成功时为 `null` |

---

## 频率限制

- 每个 `user_id` + 客户端 IP 组合每分钟最多 **5 次** 请求
- 超限返回 `429 Too Many Requests`
- 计数器每分钟自动重置

---

## 错误码汇总

| HTTP | `code` | 场景 |
|---|---|---|
| 200 | 200 | 成功 |
| 400 | 400 | URL 无效、视频无法提取、参数缺失 |
| 429 | 429 | 频率限制 |
| 500 | 500 | 服务器内部异常 |
| 502 | 502 | 上游网络请求失败 |

---

## 影视资源 — 数据来源与同步规则

> **最后更新：2026-05-31**

### 数据来源

金山文档（kdocs）逆向爬取，替代外部 API。

**配置的三个源：**

| 名称 | category | 数据量 |
|---|---|---|
| 番剧 | `anime` | ~465 条 |
| 电影 | `movie` | ~195 条 |
| 4K影视 | `4k` | ~96 条 |

### 定时同步频率

| 分类 | 频率 | 机制 |
|---|---|---|
| 番剧 | 每 15 分钟 | interval 模式，持续轮询 |
| 电影 | 每天凌晨 00:00 | cron 模式 |
| 4K影视 | 每天凌晨 00:00 | cron 模式（与电影同一任务） |

### 去重逻辑（重要）

- **去重键**：以 `quark_url`（夸克网盘 URL）作为唯一匹配键
- **匹配规则**：新爬取数据的夸克 URL 在数据库中已存在 → **先删除旧记录，再插入新记录**
- **原因**：番剧按周更新时，夸克网盘链接通常不变，但集数/状态等信息会更新，需要新数据完全替换旧数据
- **无夸克 URL 的数据**：直接插入，不做去重

### 失效标记

金山文档中已删除的条目不会被物理删除，而是标记为 `is_active = false`，用于保留已订阅用户的历史引用。

---

### 金山文档逆向原理

1. Playwright 打开金山文档分享链接
2. 拦截 `/api/v3/office/session/` 和 `/api/v3/office/collaboration/` 响应，提取 `conn_id`、`user_group`、`file_version`、`csrf_token`
3. 回退：从页面 `window.__WPSENV__` 提取参数
4. 用提取的参数调用 `POST /api/v3/office/file/{shareCode}/open/otl` 获取文档 JSON
5. 解析文档内容，提取剧名 + 百度链接 + 提取码 + 夸克链接 + 4K链接

**金山文档配置**：通过环境变量 `KDOCS_SOURCES` 或 `core/kdocs_service.py` 中的 `DEFAULT_SOURCES`：

```json
[
  {
    "name": "番剧",
    "category": "anime",
    "share_url": "https://www.kdocs.cn/l/co72a28MWkmI",
    "file_id": "434428384518",
    "share_code": "co72a28MWkmI"
  },
  {
    "name": "电影",
    "category": "movie",
    "share_url": "https://www.kdocs.cn/l/cmbapmIwVsfi",
    "file_id": "",
    "share_code": "cmbapmIwVsfi"
  },
  {
    "name": "4K影视",
    "category": "4k",
    "share_url": "https://www.kdocs.cn/l/cdv0WUisFk3x",
    "file_id": "",
    "share_code": "cdv0WUisFk3x"
  }
]
```

---

## 数据表设计

### anime_resources（影视资源表）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `anime_id` | VARCHAR(100) | 外部数据源 ID（索引） |
| `title` | VARCHAR(500) | 标题 |
| `category` | VARCHAR(20) | 类型：`anime` / `movie` / `4k`（索引） |
| `quality` | VARCHAR(20) | 画质：1080P / 4K / 720P |
| `episode` | VARCHAR(100) | 更新进度 |
| `status` | VARCHAR(20) | 状态：更新中 / 完结 / 预告 |
| `baidu_url` | TEXT | 百度网盘链接 |
| `baidu_password` | VARCHAR(20) | 百度提取码 |
| `quark_url` | TEXT | 夸克网盘链接（去重键） |
| `four_k_url` | TEXT | 4K网盘链接 |
| `source_update_time` | TIMESTAMP | 外部源最后更新时间 |
| `is_active` | BOOLEAN | 是否活跃（索引） |
| `created_at` | TIMESTAMP | 创建时间 |
| `updated_at` | TIMESTAMP | 更新时间 |

### user_subscriptions（用户订阅表）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `user_id` | UUID | 用户 ID（索引） |
| `anime_id` | VARCHAR(100) | 番剧 ID（索引） |
| `is_reminded` | BOOLEAN | 是否已催更 |
| `last_episode` | VARCHAR(100) | 用户最后看到的集数 |
| `created_at` | TIMESTAMP | 订阅时间 |

---

## PC 端对接指南

### 视频下载 — 推荐调用流程

```
1. 用户输入视频链接
2. 调用 POST /video/video_info 获取标题、封面图、可用格式
3. 展示视频信息（标题 + 封面图预览）
4. 用户点击下载 → 调用 GET /video/user_video 流式下载
```

**关键注意事项**：

| 事项 | 说明 |
|---|---|
| URL 编码 | 下载接口的 `url` 参数必须 `encodeURIComponent()`，否则含 `?` `=` 的链接会被截断 |
| 封面图跨域 | 封面图来自各平台 CDN，直接 `<img>` 标签加载即可，一般无需代理 |
| 接口耗时 | 头条（yt-dlp）和抖音（可能触发 Playwright）的视频信息获取较慢（3-15秒），PC 端应显示 loading 状态 |
| 下载进度 | 使用 `fetch + ReadableStream` + `Content-Length` 可实现下载进度条 |
| 文件名 | 从响应头 `Content-Disposition` 解析，也可用接口1返回的 `title` |

### 影视资源 — 推荐调用流程

```
1. 用户选择分类（番剧/电影/4K影视）
2. 调用 GET /anime/resources?type=anime 获取资源列表
3. 展示列表（标题、画质、集数、状态、网盘链接）
4. 支持关键词搜索：GET /anime/resources?type=anime&keyword=咒术
5. 支持分页：GET /anime/resources?type=anime&page=2&page_size=50
```

**网盘链接展示**：每个资源可能包含三种网盘链接，PC 端建议用"复制按钮"方式展示，避免直接 `<a>` 跳转（部分网盘链接需要配合提取码）。

---

## 更新日志

| 日期 | 变更内容 | 影响接口 |
|---|---|---|
| 2026-05-29 | 引入 `reverse_service.py` 统一五平台逆向下载 | 接口1、2、3 |
| 2026-05-29 | 视频信息接口新增 `cover_url` 字段 | 接口1 |
| 2026-05-29 | 影视资源数据源从外部 API 改为金山文档逆向爬取 | 接口4、5 |
| 2026-05-29 | `AnimeResource` 模型新增 `four_k_url` 字段 | 接口4 |
| 2026-05-29 | `sync_service.py` 重写，使用 `KDocsService` | 接口5 |
| 2026-05-31 | **去重逻辑改为夸克URL匹配：删除旧记录后插入新记录** | 接口4、5 |
| 2026-05-31 | **修复视频信息接口：头条/抖音/快手返回真实标题和封面图** | 接口1 |
| 2026-05-31 | 同步频率调整：电影/4K 改为每天凌晨 00:00 | 接口5 |
| 2026-05-31 | 文档重构：每个接口标注独立更新时间，新增 PC 端对接指南 | — |