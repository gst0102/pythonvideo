# 悦享互动宝 MVP 产品开发文档

## 1. 产品基础信息

### 1.1 产品名称

**悦享互动宝**

### 1.2 产品定位

**微信内容资源助手**

### 1.3 一句话介绍

用户把房源、团购、资料、图片、视频、文件发给企业微信客服，系统自动整理成小程序资源库，并支持访问追踪、客户跟进、会员付费和邀请奖励。

### 1.4 核心价值

悦享互动宝不是普通资源库，也不是传统客服工具，而是一个基于微信生态的内容资源管理与转化工具。

核心价值包括：

1. 把微信聊天里的内容自动整理成小程序资源库。
2. 把资源变成可分享、可访问、可追踪的小程序页面。
3. 记录谁看过、谁收藏、谁咨询、谁预约、谁下单。
4. 帮助房产中介、团长、资料运营者、私域用户沉淀客户线索。
5. 通过会员付费和邀请奖励形成商业闭环。

------

## 2. 产品核心闭环

```text
内容进入
  ↓
企业微信客服 / 手动添加 / 小程序发布
  ↓
自动识别与整理
  ↓
生成资源页
  ↓
分享给用户访问
  ↓
记录访问、收藏、咨询、预约、下单
  ↓
形成客户线索
  ↓
CRM 跟进
  ↓
会员付费 / 邀请奖励
```

### 2.1 四个核心闭环

```text
资源闭环：发内容 → 自动归档 → 资源库
传播闭环：资源页 → 分享海报 → 访客访问
转化闭环：访问记录 → 高意向客户 → 跟进
增长闭环：邀请好友 → 好友付费 → 现金奖励
```

------

## 3. 产品结构图

```text
悦享互动宝
│
├── 首页
│   ├── 数据概览
│   ├── 今日热门资源
│   ├── 谁看过我
│   ├── 快捷入口
│   │   ├── 房源发布
│   │   ├── 团购发布
│   │   ├── 发给客服
│   │   └── 我的资源库
│   └── 邀请会员入口
│
├── 资源库
│   ├── 资源列表
│   ├── 搜索 / 筛选
│   ├── 标签筛选
│   ├── 分类筛选
│   ├── 资源详情
│   ├── 资源编辑
│   ├── 权限设置
│   ├── 分享海报
│   ├── 访问详情
│   └── 资源失效 / 无权限页
│
├── 发给客服
│   ├── 上传图片 / 视频 / 文件
│   ├── 添加文字 / 链接
│   ├── 转发到企业微信客服
│   ├── 自动归档结果
│   └── AI 智能整理
│
├── 发布中心
│   ├── 新建房源
│   ├── 新建团购
│   ├── 新建资料包
│   ├── 手动添加资源
│   └── 资源分类管理
│
├── 访客与访问记录
│   ├── 总访问记录
│   ├── 单资源访问详情
│   ├── 访客详情
│   ├── 浏览历史
│   ├── 我的收藏
│   └── 高意向提醒
│
├── 转化功能
│   ├── 资源互动引导设置
│   ├── 咨询 / 领取资料表单
│   ├── 预约看房
│   ├── 预约成功
│   ├── 看房预约记录
│   ├── 团购接龙 / 下单
│   ├── 团购提交成功
│   └── 我的团购订单
│
├── CRM 客户管理
│   ├── 我的客户 / 线索列表
│   ├── 客户详情
│   ├── 客户标签管理
│   ├── 客户跟进记录
│   ├── 新增跟进
│   └── 待办提醒
│
├── 企业微信客服
│   ├── 客服绑定
│   ├── 自动归档配置
│   ├── 客服关键词回复
│   └── 客服消息通知
│
├── 会员中心
│   ├── 普通版
│   ├── 月会员
│   ├── 季会员
│   ├── 年会员
│   ├── 支付确认
│   ├── 开通成功
│   ├── 会员升级弹窗
│   └── 会员权益限制
│
├── 邀请奖励 / 分销收益
│   ├── 邀请奖励首页
│   ├── 邀请码 / 邀请海报
│   ├── 奖励到账通知
│   ├── 邀请奖励规则
│   ├── 提现 / 兑换会员天数
│   ├── 收益明细
│   └── 结算记录
│
├── 数据看板
│   ├── 总访问
│   ├── 新增资源
│   ├── 新增访客
│   ├── 分享次数
│   ├── 热门资源
│   ├── 高意向客户
│   └── 转化数据
│
└── 我的
    ├── 我的名片
    ├── 我的收藏
    ├── 浏览历史
    ├── 我的订单
    ├── 我的预约
    ├── 会员中心
    ├── 积分任务
    ├── 邀请奖励
    ├── 消息通知
    ├── 设置中心
    └── 授权登录 / 隐私协议
```

------

## 4. MVP 功能清单

### 4.1 MVP 1.0 必做功能

| 模块         | 功能                                     | 优先级 |
| ------------ | ---------------------------------------- | ------ |
| 登录授权     | 微信登录、手机号授权、隐私协议           | P0     |
| 资源库       | 资源列表、资源详情、搜索筛选             | P0     |
| 手动发布     | 手动添加资源、上传图片/视频/文件         | P0     |
| 企业微信客服 | 绑定客服、接收内容、自动归档             | P0     |
| 资源分类     | 房源、团购、资料包、视频、文档           | P0     |
| 标签系统     | 自定义标签、标签管理                     | P0     |
| 访问记录     | 记录浏览、收藏、分享、咨询               | P0     |
| 资源分享     | 小程序卡片、分享海报                     | P0     |
| 会员系统     | 普通 / 月 / 季 / 年会员                  | P0     |
| 支付系统     | 微信支付、订单状态                       | P0     |
| 邀请奖励     | 邀请码、邀请关系、现金奖励、会员天数奖励 | P0     |
| 收益记录     | 待结算、已发放、可提现                   | P0     |
| 消息通知     | 站内消息、奖励到账提醒                   | P0     |
| 我的页面     | 会员状态、资源数、收益入口               | P0     |

------

### 4.2 MVP 1.1 建议加入

| 模块     | 功能                             |
| -------- | -------------------------------- |
| 房产场景 | 新建房源、房源详情、预约看房     |
| 团购场景 | 新建团购、团购接龙、我的团购订单 |
| 资料包   | 资料包详情、资料领取             |
| CRM      | 客户列表、客户详情、跟进记录     |
| 数据看板 | 访问趋势、热门资源、高意向客户   |
| AI 整理  | 自动标题、摘要、标签、文案       |

------

### 4.3 MVP 2.0 后续增强

| 模块     | 功能                                 |
| -------- | ------------------------------------ |
| 自动回复 | 企业微信关键词自动回复资源           |
| 高级 CRM | 客户分组、成交记录、导出客户         |
| 分销增强 | 邀请排行榜、活动任务、分销海报       |
| 自动推送 | 订阅消息、企微客服消息、站内消息联动 |
| 数据分析 | 转化率、渠道效果、会员转化           |

------

## 5. 核心业务流程

### 5.1 资源发布流程

```text
用户手动添加 / 发给企业微信客服
        ↓
系统接收图片、视频、文字、文件
        ↓
AI / 规则识别内容类型
        ↓
生成标题、分类、标签
        ↓
创建资源
        ↓
进入资源库
        ↓
生成资源详情页
        ↓
支持分享 / 海报 / 访问追踪
```

------

### 5.2 访问追踪流程

```text
访客打开资源页
        ↓
判断是否登录
        ↓
记录访问行为
        ↓
记录资源 ID、访客 ID、来源、时间、行为
        ↓
如果重复访问 / 收藏 / 咨询
        ↓
生成高意向提醒
        ↓
进入客户线索池
```

------

### 5.3 邀请奖励流程

```text
A 用户生成邀请码 / 邀请海报
        ↓
B 用户通过邀请链接进入
        ↓
B 登录后绑定邀请关系
        ↓
B 首次开通会员
        ↓
系统生成奖励记录
        ↓
奖励进入待结算
        ↓
结算完成后变为可提现 / 已发放
        ↓
A 收到站内消息 / 订阅消息 / 企业微信客服提醒
```

------

## 6. 会员体系设计

### 6.1 会员等级

| 会员类型 | 价格建议   | 说明       |
| -------- | ---------- | ---------- |
| 普通版   | 0 元       | 基础使用   |
| 月会员   | 19.9 元/月 | 轻度付费   |
| 季会员   | 49.9 元/季 | 推荐套餐   |
| 年会员   | 168 元/年  | 最划算套餐 |

------

### 6.2 会员权益

| 权益             | 普通版    | 月会员     | 季会员      | 年会员          |
| ---------------- | --------- | ---------- | ----------- | --------------- |
| 资源容量         | 10 个资源 | 500 个资源 | 2000 个资源 | 10000 个资源    |
| 自定义标签       | 1 个      | 10 个      | 50 个       | 不限            |
| 企业微信自动归档 | 不支持    | 支持       | 支持        | 支持            |
| AI 智能整理      | 不支持    | 基础整理   | 智能分类    | 智能分类 + 推荐 |
| 访问记录保存     | 3 天      | 30 天      | 90 天       | 365 天          |
| 高意向提醒       | 不支持    | 每日 10 条 | 每日 50 条  | 每日 100 条     |
| 分享海报         | 不支持    | 支持       | 支持        | 支持            |
| 专属客服         | 不支持    | 工作日服务 | 优先服务    | 专属 1v1 服务   |

------

## 7. 邀请奖励 / 分销收益设计

### 7.1 模块定位

邀请奖励是第一版重点模块，用来驱动用户传播和会员转化。

页面建议使用名称：

- 邀请奖励
- 我的收益
- 奖励到账
- 提现 / 兑换

尽量避免直接使用“分销”“返佣”等敏感词。

------

### 7.2 第一版奖励规则

| 好友开通 | 现金奖励 | 会员天数奖励 |
| -------- | -------- | ------------ |
| 月会员   | 2 元     | 3 天         |
| 季会员   | 8 元     | 10 天        |
| 年会员   | 18 元    | 30 天        |

------

### 7.3 结算规则

```text
好友成功支付后，奖励进入待结算。
订单满 7 天未退款，奖励变为可提现。
满 10 元可提现到微信零钱。
如果好友退款，对应奖励自动失效。
异常邀请、刷单、虚假交易，奖励冻结。
```

------

### 7.4 奖励状态

| 状态         | 说明   |
| ------------ | ------ |
| pending      | 待结算 |
| settled      | 已结算 |
| withdrawable | 可提现 |
| paid         | 已发放 |
| invalid      | 已失效 |

------

### 7.5 奖励到账通知

奖励到账后，需要同时写入三个通知渠道：

#### 1. 小程序站内消息

必须做，最稳定。

展示位置：

- 消息通知页
- 我的页面红点
- 收益页弹窗
- 奖励到账详情页

#### 2. 小程序订阅消息

用户授权后才能推送。

建议在以下动作引导订阅：

- 点击邀请好友
- 点击开启奖励提醒
- 点击查看收益
- 点击生成邀请海报
- 点击开通会员

#### 3. 企业微信客服通知

用户添加/绑定企业微信客服后，可通过客服会话发送奖励通知。

适合推送：

- 好友开通会员
- 奖励到账
- 奖励待结算
- 可提现提醒
- 提现成功通知

------

## 8. 数据库表设计

### 8.1 用户表：`users`

| 字段              | 类型     | 说明                          |
| ----------------- | -------- | ----------------------------- |
| id                | bigint   | 用户 ID                       |
| openid            | varchar  | 微信 openid                   |
| unionid           | varchar  | 微信 unionid                  |
| nickname          | varchar  | 昵称                          |
| avatar_url        | varchar  | 头像                          |
| phone             | varchar  | 手机号                        |
| role              | varchar  | user / admin                  |
| invite_code       | varchar  | 用户的邀请码                  |
| invited_by        | bigint   | 邀请人 user_id                |
| member_level      | varchar  | free / month / quarter / year |
| member_expired_at | datetime | 会员到期时间                  |
| status            | tinyint  | 状态                          |
| created_at        | datetime | 创建时间                      |
| updated_at        | datetime | 更新时间                      |

------

### 8.2 资源表：`resources`

| 字段                 | 类型     | 说明                                                   |
| -------------------- | -------- | ------------------------------------------------------ |
| id                   | bigint   | 资源 ID                                                |
| user_id              | bigint   | 创建者                                                 |
| title                | varchar  | 资源标题                                               |
| description          | text     | 资源描述                                               |
| type                 | varchar  | house / group_buy / package / video / document / other |
| category_id          | bigint   | 分类 ID                                                |
| cover_url            | varchar  | 封面图                                                 |
| source               | varchar  | manual / wecom / ai                                    |
| visibility           | varchar  | public / private / member / password                   |
| allow_share          | tinyint  | 是否允许分享                                           |
| allow_download       | tinyint  | 是否允许下载                                           |
| allow_visitor_record | tinyint  | 是否记录访客                                           |
| status               | varchar  | draft / published / offline / expired / deleted        |
| view_count           | int      | 浏览数                                                 |
| collect_count        | int      | 收藏数                                                 |
| share_count          | int      | 分享数                                                 |
| consult_count        | int      | 咨询数                                                 |
| created_at           | datetime | 创建时间                                               |
| updated_at           | datetime | 更新时间                                               |

------

### 8.3 资源附件表：`resource_files`

| 字段        | 类型     | 说明                             |
| ----------- | -------- | -------------------------------- |
| id          | bigint   | 附件 ID                          |
| resource_id | bigint   | 资源 ID                          |
| file_type   | varchar  | image / video / pdf / doc / xlsx |
| file_url    | varchar  | 文件地址                         |
| file_name   | varchar  | 文件名                           |
| file_size   | bigint   | 文件大小                         |
| sort_order  | int      | 排序                             |
| created_at  | datetime | 创建时间                         |

------

### 8.4 分类表：`categories`

| 字段       | 类型    | 说明         |
| ---------- | ------- | ------------ |
| id         | bigint  | 分类 ID      |
| user_id    | bigint  | 所属用户     |
| name       | varchar | 分类名称     |
| icon       | varchar | 图标         |
| color      | varchar | 颜色         |
| sort_order | int     | 排序         |
| is_system  | tinyint | 是否系统分类 |
| status     | tinyint | 状态         |

------

### 8.5 标签表：`tags`

| 字段       | 类型     | 说明                |
| ---------- | -------- | ------------------- |
| id         | bigint   | 标签 ID             |
| user_id    | bigint   | 所属用户            |
| name       | varchar  | 标签名              |
| color      | varchar  | 标签颜色            |
| type       | varchar  | resource / customer |
| use_count  | int      | 使用次数            |
| created_at | datetime | 创建时间            |

------

### 8.6 资源标签关联表：`resource_tags`

| 字段        | 类型   | 说明    |
| ----------- | ------ | ------- |
| id          | bigint | ID      |
| resource_id | bigint | 资源 ID |
| tag_id      | bigint | 标签 ID |

------

### 8.7 访问记录表：`resource_visits`

| 字段        | 类型     | 说明                                        |
| ----------- | -------- | ------------------------------------------- |
| id          | bigint   | 访问 ID                                     |
| resource_id | bigint   | 资源 ID                                     |
| owner_id    | bigint   | 资源拥有者                                  |
| visitor_id  | bigint   | 访问者                                      |
| action      | varchar  | view / collect / share / consult / download |
| source      | varchar  | share / qrcode / wecom / search             |
| ip          | varchar  | IP                                          |
| user_agent  | varchar  | 设备信息                                    |
| duration    | int      | 停留时间                                    |
| created_at  | datetime | 访问时间                                    |

------

### 8.8 收藏表：`collections`

| 字段        | 类型     | 说明     |
| ----------- | -------- | -------- |
| id          | bigint   | ID       |
| user_id     | bigint   | 用户 ID  |
| resource_id | bigint   | 资源 ID  |
| created_at  | datetime | 收藏时间 |

------

### 8.9 房源表：`houses`

| 字段           | 类型    | 说明                              |
| -------------- | ------- | --------------------------------- |
| id             | bigint  | 房源 ID                           |
| resource_id    | bigint  | 对应资源                          |
| community_name | varchar | 小区名称                          |
| house_type     | varchar | 户型                              |
| area           | decimal | 面积                              |
| total_price    | decimal | 总价                              |
| rent_price     | decimal | 租金                              |
| floor          | varchar | 楼层                              |
| decoration     | varchar | 装修                              |
| address        | varchar | 地址                              |
| contact_name   | varchar | 联系人                            |
| contact_phone  | varchar | 联系电话                          |
| status         | varchar | selling / rented / sold / offline |

------

### 8.10 看房预约表：`house_appointments`

| 字段             | 类型     | 说明                                      |
| ---------------- | -------- | ----------------------------------------- |
| id               | bigint   | 预约 ID                                   |
| house_id         | bigint   | 房源 ID                                   |
| resource_id      | bigint   | 资源 ID                                   |
| user_id          | bigint   | 预约用户                                  |
| owner_id         | bigint   | 房源发布者                                |
| name             | varchar  | 预约人                                    |
| phone            | varchar  | 手机号                                    |
| appointment_time | datetime | 预约时间                                  |
| people_count     | int      | 看房人数                                  |
| remark           | text     | 备注                                      |
| status           | varchar  | pending / confirmed / visited / cancelled |
| created_at       | datetime | 创建时间                                  |

------

### 8.11 团购表：`group_buys`

| 字段           | 类型     | 说明                               |
| -------------- | -------- | ---------------------------------- |
| id             | bigint   | 团购 ID                            |
| resource_id    | bigint   | 对应资源                           |
| owner_id       | bigint   | 发布者                             |
| title          | varchar  | 团购标题                           |
| start_time     | datetime | 开团时间                           |
| end_time       | datetime | 截止时间                           |
| pickup_address | varchar  | 自提点                             |
| delivery_type  | varchar  | pickup / delivery / both           |
| min_people     | int      | 起团人数                           |
| joined_count   | int      | 已参与人数                         |
| status         | varchar  | draft / active / ended / cancelled |

------

### 8.12 团购商品表：`group_buy_items`

| 字段         | 类型    | 说明    |
| ------------ | ------- | ------- |
| id           | bigint  | 商品 ID |
| group_buy_id | bigint  | 团购 ID |
| name         | varchar | 商品名  |
| image_url    | varchar | 图片    |
| price        | decimal | 单价    |
| unit         | varchar | 单位    |
| stock        | int     | 库存    |
| sort_order   | int     | 排序    |

------

### 8.13 团购订单表：`group_buy_orders`

| 字段            | 类型     | 说明                                            |
| --------------- | -------- | ----------------------------------------------- |
| id              | bigint   | 订单 ID                                         |
| order_no        | varchar  | 订单号                                          |
| group_buy_id    | bigint   | 团购 ID                                         |
| user_id         | bigint   | 下单用户                                        |
| owner_id        | bigint   | 团长                                            |
| total_amount    | decimal  | 总金额                                          |
| discount_amount | decimal  | 优惠                                            |
| pay_amount      | decimal  | 实付                                            |
| pickup_name     | varchar  | 联系人                                          |
| pickup_phone    | varchar  | 手机号                                          |
| pickup_address  | varchar  | 自提点                                          |
| status          | varchar  | pending / paid / picked / completed / cancelled |
| created_at      | datetime | 创建时间                                        |

------

### 8.14 会员订单表：`member_orders`

| 字段           | 类型     | 说明                      |
| -------------- | -------- | ------------------------- |
| id             | bigint   | 订单 ID                   |
| order_no       | varchar  | 订单号                    |
| user_id        | bigint   | 用户 ID                   |
| plan           | varchar  | month / quarter / year    |
| amount         | decimal  | 支付金额                  |
| pay_status     | varchar  | pending / paid / refunded |
| transaction_id | varchar  | 微信支付交易号            |
| paid_at        | datetime | 支付时间                  |
| created_at     | datetime | 创建时间                  |

------

### 8.15 邀请关系表：`invite_relations`

| 字段        | 类型     | 说明                   |
| ----------- | -------- | ---------------------- |
| id          | bigint   | ID                     |
| inviter_id  | bigint   | 邀请人                 |
| invitee_id  | bigint   | 被邀请人               |
| invite_code | varchar  | 邀请码                 |
| source      | varchar  | poster / link / qrcode |
| bind_status | varchar  | bound / invalid        |
| created_at  | datetime | 绑定时间               |

------

### 8.16 邀请奖励表：`invite_rewards`

| 字段            | 类型     | 说明                                              |
| --------------- | -------- | ------------------------------------------------- |
| id              | bigint   | 奖励 ID                                           |
| inviter_id      | bigint   | 邀请人                                            |
| invitee_id      | bigint   | 被邀请人                                          |
| member_order_id | bigint   | 会员订单                                          |
| reward_cash     | decimal  | 现金奖励                                          |
| reward_days     | int      | 会员天数奖励                                      |
| status          | varchar  | pending / settled / withdrawable / paid / invalid |
| settle_at       | datetime | 结算时间                                          |
| paid_at         | datetime | 发放时间                                          |
| created_at      | datetime | 创建时间                                          |

------

### 8.17 提现表：`withdraw_orders`

| 字段         | 类型     | 说明                       |
| ------------ | -------- | -------------------------- |
| id           | bigint   | 提现 ID                    |
| user_id      | bigint   | 用户 ID                    |
| amount       | decimal  | 提现金额                   |
| method       | varchar  | wechat_wallet              |
| status       | varchar  | pending / success / failed |
| remark       | text     | 备注                       |
| created_at   | datetime | 创建时间                   |
| completed_at | datetime | 到账时间                   |

------

### 8.18 客户线索表：`customers`

| 字段           | 类型     | 说明                                           |
| -------------- | -------- | ---------------------------------------------- |
| id             | bigint   | 客户 ID                                        |
| owner_id       | bigint   | 资源拥有者                                     |
| user_id        | bigint   | 客户对应用户                                   |
| name           | varchar  | 客户名称                                       |
| phone          | varchar  | 手机                                           |
| score          | int      | 意向分                                         |
| status         | varchar  | new / following / consulted / appointed / deal |
| last_active_at | datetime | 最近活跃                                       |
| source         | varchar  | resource / share / wecom / order               |
| remark         | text     | 备注                                           |
| created_at     | datetime | 创建时间                                       |

------

### 8.19 客户跟进表：`customer_followups`

| 字段             | 类型     | 说明                                        |
| ---------------- | -------- | ------------------------------------------- |
| id               | bigint   | 跟进 ID                                     |
| customer_id      | bigint   | 客户 ID                                     |
| owner_id         | bigint   | 所属用户                                    |
| method           | varchar  | phone / wecom / message / offline           |
| result           | varchar  | interested / appointed / no_interest / deal |
| content          | text     | 跟进内容                                    |
| next_follow_time | datetime | 下次跟进时间                                |
| created_at       | datetime | 创建时间                                    |

------

### 8.20 消息通知表：`notifications`

| 字段       | 类型     | 说明                                     |
| ---------- | -------- | ---------------------------------------- |
| id         | bigint   | 消息 ID                                  |
| user_id    | bigint   | 接收人                                   |
| type       | varchar  | visit / reward / order / member / system |
| title      | varchar  | 标题                                     |
| content    | text     | 内容                                     |
| link_type  | varchar  | 跳转类型                                 |
| link_id    | bigint   | 跳转 ID                                  |
| is_read    | tinyint  | 是否已读                                 |
| created_at | datetime | 创建时间                                 |

------

## 9. 接口清单

### 9.1 用户与登录

| 方法 | 接口                     | 说明         |
| ---- | ------------------------ | ------------ |
| POST | `/api/auth/wechat-login` | 微信登录     |
| POST | `/api/auth/bind-phone`   | 绑定手机号   |
| GET  | `/api/user/profile`      | 获取用户信息 |
| PUT  | `/api/user/profile`      | 更新用户资料 |

------

### 9.2 资源库

| 方法   | 接口                             | 说明         |
| ------ | -------------------------------- | ------------ |
| GET    | `/api/resources`                 | 获取资源列表 |
| POST   | `/api/resources`                 | 新建资源     |
| GET    | `/api/resources/{id}`            | 获取资源详情 |
| PUT    | `/api/resources/{id}`            | 编辑资源     |
| DELETE | `/api/resources/{id}`            | 删除资源     |
| PUT    | `/api/resources/{id}/visibility` | 修改权限     |
| POST   | `/api/resources/{id}/share`      | 分享资源     |
| POST   | `/api/resources/{id}/collect`    | 收藏资源     |
| DELETE | `/api/resources/{id}/collect`    | 取消收藏     |

------

### 9.3 文件上传

| 方法 | 接口                | 说明     |
| ---- | ------------------- | -------- |
| POST | `/api/upload/image` | 上传图片 |
| POST | `/api/upload/video` | 上传视频 |
| POST | `/api/upload/file`  | 上传文件 |

------

### 9.4 企业微信客服

| 方法 | 接口                          | 说明             |
| ---- | ----------------------------- | ---------------- |
| GET  | `/api/wecom/config`           | 获取企微绑定配置 |
| POST | `/api/wecom/bind`             | 绑定企微客服     |
| POST | `/api/wecom/message-callback` | 企业微信消息回调 |
| POST | `/api/wecom/archive`          | 自动归档资源     |
| PUT  | `/api/wecom/archive-config`   | 更新自动归档设置 |

------

### 9.5 标签与分类

| 方法   | 接口                   | 说明     |
| ------ | ---------------------- | -------- |
| GET    | `/api/categories`      | 分类列表 |
| POST   | `/api/categories`      | 新建分类 |
| PUT    | `/api/categories/{id}` | 编辑分类 |
| DELETE | `/api/categories/{id}` | 删除分类 |
| GET    | `/api/tags`            | 标签列表 |
| POST   | `/api/tags`            | 新建标签 |
| PUT    | `/api/tags/{id}`       | 编辑标签 |
| DELETE | `/api/tags/{id}`       | 删除标签 |

------

### 9.6 访问记录

| 方法 | 接口                         | 说明           |
| ---- | ---------------------------- | -------------- |
| POST | `/api/visits/record`         | 记录访问行为   |
| GET  | `/api/visits`                | 访问记录列表   |
| GET  | `/api/resources/{id}/visits` | 单资源访问详情 |
| GET  | `/api/visitors/{id}`         | 访客详情       |
| GET  | `/api/history`               | 浏览历史       |

------

### 9.7 房源

| 方法 | 接口                            | 说明         |
| ---- | ------------------------------- | ------------ |
| POST | `/api/houses`                   | 新建房源     |
| GET  | `/api/houses/{id}`              | 房源详情     |
| PUT  | `/api/houses/{id}`              | 编辑房源     |
| POST | `/api/houses/{id}/appointment`  | 预约看房     |
| GET  | `/api/appointments`             | 看房预约记录 |
| PUT  | `/api/appointments/{id}/status` | 修改预约状态 |

------

### 9.8 团购

| 方法 | 接口                                | 说明         |
| ---- | ----------------------------------- | ------------ |
| POST | `/api/group-buys`                   | 新建团购     |
| GET  | `/api/group-buys/{id}`              | 团购详情     |
| PUT  | `/api/group-buys/{id}`              | 编辑团购     |
| POST | `/api/group-buys/{id}/orders`       | 团购下单     |
| GET  | `/api/group-buy-orders`             | 我的团购订单 |
| GET  | `/api/group-buy-orders/{id}`        | 订单详情     |
| PUT  | `/api/group-buy-orders/{id}/status` | 更新订单状态 |

------

### 9.9 会员与支付

| 方法 | 接口                 | 说明         |
| ---- | -------------------- | ------------ |
| GET  | `/api/member/plans`  | 会员套餐     |
| POST | `/api/member/orders` | 创建会员订单 |
| POST | `/api/pay/wechat`    | 发起微信支付 |
| POST | `/api/pay/notify`    | 微信支付回调 |
| GET  | `/api/member/status` | 会员状态     |
| POST | `/api/member/renew`  | 续费会员     |

------

### 9.10 邀请奖励 / 分销收益

| 方法 | 接口                               | 说明         |
| ---- | ---------------------------------- | ------------ |
| GET  | `/api/invite/overview`             | 邀请收益概览 |
| GET  | `/api/invite/code`                 | 获取邀请码   |
| POST | `/api/invite/bind`                 | 绑定邀请关系 |
| GET  | `/api/invite/rewards`              | 奖励明细     |
| GET  | `/api/invite/rules`                | 奖励规则     |
| POST | `/api/invite/poster`               | 生成邀请海报 |
| POST | `/api/withdraw`                    | 发起提现     |
| GET  | `/api/withdraw/orders`             | 提现记录     |
| POST | `/api/reward/exchange-member-days` | 兑换会员天数 |

------

### 9.11 CRM 客户

| 方法 | 接口                            | 说明     |
| ---- | ------------------------------- | -------- |
| GET  | `/api/customers`                | 客户列表 |
| GET  | `/api/customers/{id}`           | 客户详情 |
| PUT  | `/api/customers/{id}`           | 更新客户 |
| POST | `/api/customers/{id}/followups` | 新增跟进 |
| GET  | `/api/customers/{id}/followups` | 跟进记录 |
| GET  | `/api/tasks`                    | 待办提醒 |
| PUT  | `/api/tasks/{id}/done`          | 完成待办 |

------

### 9.12 消息通知

| 方法 | 接口                           | 说明         |
| ---- | ------------------------------ | ------------ |
| GET  | `/api/notifications`           | 消息列表     |
| PUT  | `/api/notifications/{id}/read` | 标记已读     |
| POST | `/api/subscribe-message/apply` | 申请订阅消息 |
| POST | `/api/subscribe-message/send`  | 发送订阅消息 |

------

### 9.13 AI 整理

| 方法 | 接口                           | 说明         |
| ---- | ------------------------------ | ------------ |
| POST | `/api/ai/recognize`            | 识别内容     |
| POST | `/api/ai/generate-title`       | 生成标题     |
| POST | `/api/ai/generate-tags`        | 生成标签     |
| POST | `/api/ai/generate-summary`     | 生成摘要     |
| POST | `/api/ai/generate-copywriting` | 生成推广文案 |

------

## 10. 开发优先级

### 10.1 P0：必须先做

目标：跑通核心商业闭环。

```text
登录授权
会员系统
微信支付
邀请关系
邀请奖励
资源库
手动添加资源
企业微信客服接收内容
自动归档
访问记录
分享资源
消息通知
```

| 功能                   | 优先级 |
| ---------------------- | ------ |
| 微信登录 / 手机号授权  | P0     |
| 资源库列表 / 详情      | P0     |
| 手动添加资源           | P0     |
| 企业微信客服绑定       | P0     |
| 企业微信消息回调       | P0     |
| 自动归档资源           | P0     |
| 标签 / 分类            | P0     |
| 浏览 / 收藏 / 分享记录 | P0     |
| 会员套餐               | P0     |
| 微信支付               | P0     |
| 会员开通成功           | P0     |
| 邀请码 / 邀请海报      | P0     |
| 邀请关系绑定           | P0     |
| 邀请奖励计算           | P0     |
| 奖励到账通知           | P0     |
| 收益页 / 提现页        | P0     |

------

### 10.2 P1：第一版增强

目标：让房产和团购两个场景完整可用。

| 功能                | 优先级 |
| ------------------- | ------ |
| 新建房源            | P1     |
| 房源详情            | P1     |
| 预约看房            | P1     |
| 预约记录            | P1     |
| 新建团购            | P1     |
| 团购详情            | P1     |
| 团购接龙 / 下单     | P1     |
| 团购订单            | P1     |
| 资料包详情          | P1     |
| 咨询 / 领取资料表单 | P1     |
| 资源分享海报        | P1     |
| 浏览历史            | P1     |
| 我的收藏            | P1     |
| 资源权限设置        | P1     |

------

### 10.3 P2：运营与 CRM

目标：提升用户粘性和转化。

| 功能           | 优先级 |
| -------------- | ------ |
| 客户列表       | P2     |
| 客户详情       | P2     |
| 客户标签管理   | P2     |
| 跟进记录       | P2     |
| 新增跟进       | P2     |
| 待办提醒       | P2     |
| 数据看板       | P2     |
| 高意向客户提醒 | P2     |
| 消息通知中心   | P2     |

------

### 10.4 P3：AI 与自动化

目标：提升高级会员价值。

| 功能               | 优先级 |
| ------------------ | ------ |
| AI 标题生成        | P3     |
| AI 标签生成        | P3     |
| AI 摘要生成        | P3     |
| AI 推广文案        | P3     |
| 客服关键词自动回复 | P3     |
| 自动回复规则       | P3     |
| 数据导出           | P3     |

------

## 11. 第一版建议开发顺序

### 第 1 阶段：基础框架

```text
用户登录
用户表
资源表
上传文件
资源库
资源详情
标签分类
```

------

### 第 2 阶段：企业微信客服归档

```text
绑定企业微信客服
接收客服消息
解析图片 / 视频 / 文字 / 文件
生成资源
自动归档结果
```

------

### 第 3 阶段：会员付费

```text
会员套餐
微信支付
会员订单
会员状态
会员权益限制
升级弹窗
```

------

### 第 4 阶段：邀请奖励

```text
邀请码
邀请海报
邀请关系绑定
好友开通会员
现金奖励
会员天数奖励
待结算
提现
奖励到账通知
```

------

### 第 5 阶段：房产 / 团购场景

```text
新建房源
房源详情
预约看房
新建团购
团购详情
团购接龙
团购订单
```

------

### 第 6 阶段：访问追踪和 CRM

```text
访问记录
访客详情
客户列表
客户跟进
待办提醒
数据看板
```

------

## 12. 最小可上线版本建议

真正第一版上线，建议只做以下功能：

```text
1. 登录授权
2. 资源库
3. 手动添加资源
4. 发给企业微信客服自动归档
5. 资源分享
6. 访问记录
7. 会员付费
8. 邀请奖励
9. 收益提现
10. 消息通知
```

第一版先验证：

```text
用户愿不愿意为「资源自动整理 + 谁看过 + 邀请奖励」付费。
```

如果数据好，再继续强化房产、团购、CRM 和 AI。

------

## 13. 风险与注意事项

### 13.1 邀请奖励风险控制

第一版建议：

1. 只做一级邀请奖励。
2. 不做多级分销。
3. 不做团队层级。
4. 不做拉人头排行榜。
5. 奖励基于真实会员支付。
6. 退款后奖励失效。
7. 设置 7 天待结算。
8. 满 10 元可提现。
9. 平台保留异常邀请审核权。
10. 页面文案用“邀请奖励”，不要用“分销返佣”。

------

### 13.2 访问记录与隐私

因为产品涉及：

- 谁看过
- 访问记录
- 收藏
- 预约
- 手机号
- 企业微信客服

所以必须提供：

1. 隐私政策。
2. 用户协议。
3. 手机号授权说明。
4. 访问记录用途说明。
5. 用户数据删除/注销入口。

------

### 13.3 企业微信客服限制

企业微信客服通知应作为补充通知，不应高频骚扰用户。

建议只推送强相关消息：

- 奖励到账
- 会员开通成功
- 资源归档成功
- 高意向客户提醒
- 提现成功
- 预约/订单提醒

------

## 14. 当前版本产品结论

悦享互动宝可以收敛为：

```text
基于企业微信客服的内容资源库 + 访问追踪 + 会员付费 + 邀请奖励系统。
```

第一版核心不是把所有行业都做完，而是先跑通四个闭环：

```text
资源闭环：发内容 → 自动归档 → 资源库
传播闭环：资源页 → 分享海报 → 访客访问
转化闭环：访问记录 → 高意向客户 → 跟进
增长闭环：邀请好友 → 好友付费 → 现金奖励
```

只要这四个闭环跑通，产品就具备真实商业化基础。