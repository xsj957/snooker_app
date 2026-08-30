# 斯诺克大师国内App — 数据库完整文档

> **数据库**: supervisions（121.40.243.17:3306）
> **账号**: linjiakun / 密码: Ljk@123456
> **生成日期**: 2026-07-28（最后更新: 2026-08-31）
> **数据来源**: 直接读取 information_schema 字段注释 + 实际数据分析

---

## 一、数据库概览

| 数据库 | 表数量 | 业务定位 |
|--------|--------|---------|
| **supervisions** | 214 张 | 核心业务库：视频、支付、用户、比赛 |

---

## 二、视频业务核心表（supervisions 库）

### 2.1 表关系图

```
video_list (视频目录)
    │
    ├── video_order (视频解锁订单) ←→ video_combo_order (套餐订单)
    │       │                              │
    │       ├── video_coupon_record        ── video_combo (套餐定义)
    │       │
    │       ├── video_source (原片地址)
    │       ├── video_event (播放事件)
    │       ├── video_refund (退款记录)
    │       └── video_client_status (客户端状态)
    │
    └── video_price (定价规则)
```

### 2.2 video_list — 视频目录表（1438 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint(20) unsigned zerofill | 自增主键，视频 ID |
| competition_id | varchar(36) | 赛 ID |
| inning_id | int | 局 ID |
| frame_index | int | 第几集直播 |
| **category** | varchar(255) | **视频分类**：精彩集锦/单杆30+/单杆50+/局视频等 |
| content | varchar(300) | 视频内容 |
| **price** | int | **视频价格（单位：分）** |
| **duration** | int | **时长（秒）** |
| create_time | datetime | 创建时间 |
| nickname_a / nickname_b | varchar(255) | 左方/右方昵称 |
| buy_times | int | 购买次数 |
| amount | int | 累计收款（单位：分） |
| **status** | int | **视频状态**：0=待解锁, 1=已购买, 2=已删除 |
| last_pay_time | datetime | 最后支付时间 |
| merchant_address_id | int | 商户地址 ID |
| table_number | varchar(64) | 桌台编号 |
| flag | bigint | 帧码，用于标识同一时刻的多个视频 |
| path | varchar(2600) | 源视频文件在工控机上的存储路径 |
| player | int | 0=左方, 1=右方 |
| live | int | 1=直播连接 |
| replay / replay_duration | int | 回放次数 / 回放视频时长 |
| break_score | int | 最高分 |
| turnover / turnover_duration | int | 失败次数 / 失败时长 |

### 2.3 video_order — 视频解锁订单表（1004 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键，订单 ID（当前 1942） |
| user_id | varchar(36) | 用户 ID（关联 ten_user.id） |
| union_id | varchar(100) | 微信 UnionID |
| **video_id** | bigint | **视频 ID（video_list 的 ID）** |
| create_time / pay_time | datetime | 创建/支付时间 |
| **pay_status** | varchar(255) | **支付状态**：支付成功/支付失败/待支付 |
| url | varchar(300) | 视频观看地址 |
| wx_orderid | varchar(100) | 传给微信的订单编号 |
| amount | int | 支付金额（分） |
| transaction_id | varchar(40) | 微信支付订单号 |
| surplus | int | 1=多余的，同一用户点击多次购买就会产生多次订单 |
| **video_status** | tinyint | **视频状态**：0=待处理, 1=工控机已生成, 2=工控机未合成 |
| remark | varchar(255) | 备注 |
| upload_time | datetime | 链接上传时间 |
| left_play_times | int | 剩余播放次数（默认 50） |
| size | int | 视频大小 MB |
| cover | varchar(300) | 封面 |
| duration | int | 时长（秒） |
| combo_order_id | bigint | 套餐订单号 |
| to_club_news | tinyint | 0=不推送, 1=推送到俱乐部动态 |
| is_viewed | tinyint(1) | 是否已观看：0=未观看, 1=已观看 |
| view_time | datetime | 首次观看时间 |
| asked_once | tinyint | 微信是否弹出过询问推送对话框：0=未弹出, 1=已经弹过 |
| merchant_address_id | int | 商户地址 ID |
| **pay_channel** | tinyint | **支付渠道**：0=小程序android, 1=小程序ios, 2=app_android, 3=app_ios |
| **refund_status** | tinyint | **退款状态**：0=未退款, 1=已申请退款, 2=已退款, 3=退款失败 |
| bin_url | varchar(128) | 视频 bin 文件的 URL |

**当前数据分布**：

| video_status | pay_status | 数量 |
|-------------|-----------|------|
| 0 | 支付成功 | 879 |
| 0 | 未支付 | 117 |
| 0 | 空 | 6 |
| 0 | 支付失败 | 1 |
| 2 | 未支付 | 1 |

> **⚠️ 注意**：`video_status` 大部分为 0，与数据库注释不一致。0 可能是历史遗留值或新增的"待解锁"状态。国内 App 本地制作新增的状态目前数据库中尚未出现。

### 2.4 video_combo — 视频券套餐定义表（3 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键 |
| **price** | int | **价格（单位：分）** |
| **video_count** | int | **视频数量（券张数）** |
| **single_price** | int | **综合单价（分）** |
| **save_money** | int | **节省 X 元（分）** |
| status | int | 状态：1=正常, 0=无效 |
| display_order | int | 按从小到大排列 |
| **month** | int | **套餐有效期（X 个月）** |

**当前数据**：

| ID | price(分) | video_count | single_price(分) | save_money(分) | month |
|----|-----------|-------------|-----------------|---------------|-------|
| 1 | 100 (1元) | 3 | 330 | 2000 | 1 |
| 2 | 101 (约1元) | 12 | 250 | 9000 | 3 |
| 3 | 102 (约1元) | 60 | 200 | 48000 | 12 |

> **⚠️ 数据异常**：price 字段值为 100/101/102 分（约 1 元），与 PRD 文档的 9.9/29.9/118.8 元严重不符。可能是测试环境数据。

### 2.5 video_combo_order — 套餐订单表（2484 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 自增主键 |
| combo_id | int | 套餐 ID |
| video_count | int | 套餐视频数 |
| used_count | int | 视频使用数量 |
| create_time / pay_time | datetime | 创建/支付时间 |
| pay_status | varchar(255) | 支付状态：支付成功/支付失败 |
| wx_orderid | varchar(100) | 传给微信的订单编号 |
| amount | int | 支付金额（单位：分） |
| transaction_id | varchar(40) | 微信支付订单号 |
| user_id | varchar(36) | 用户 ID（关联 ten_user.id） |
| union_id | varchar(100) | 微信 UnionID |
| **video_order_id** | int | **视频订单 ID** |
| **end_time** | datetime | **过期时间（23:59:59 之前）** |
| **channel** | int | **渠道类型**：2=H5, 其他值=小程序 |
| **pay_channel** | tinyint | **支付渠道**：0=android, 1=ios |
| **refund_status** | tinyint | **退款状态**：0=未退款, 1=已申请退款, 2=已退款, 3=退款失败 |

> **⚠️ 注意**：`channel` 字段注释为"2=H5, 其他值=小程序"，**没有 App 的值**。App 端购买记录可能需要后端新增渠道值。`pay_channel` 只有 0/1 两个值（android/ios），与 `video_order.pay_channel` 的 0~3 四个值不同。

### 2.6 video_coupon_record — 视频券记录表（377 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 自增主键，流水 ID |
| user_id | varchar(36) | 用户 ID |
| **coupon_id** | int | **优惠券 ID**：1=套餐的专享优惠券, 2=7天打卡活动的券 |
| draw_time | datetime | 领取时间 |
| end_date | datetime | 过期时间 |
| **status** | tinyint | **状态**：0=有效, 1=已使用, 2=已过期 |
| order_id | int | 对应视频订单 ID |

### 2.7 video_price — 视频定价规则表（60+ 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键 |
| **category** | int | **视频分类**：1=局视频；30/40/50/60/70/80/90/100/110/120/130/140=对应单杆30+到单杆140+ |
| **base_price** | int | **基础价格（单位：分）** |
| **discount_price** | int | **优惠价格（单位：分）** |
| **discount** | int | **折扣，10 表示 1 折** |
| latest_begin_time / latest_end_time | datetime | 最新优惠开始/结束时间 |
| **apply_times** | int | **最后应用次数**，用于恢复基础价格 |
| **is_regular** | int | **1=固定项目不能编辑，非1=可编辑** |
| create_time / create_user | datetime/varchar | 创建时间/创建人 |
| update_time / update_user | datetime/varchar | 更新时间/更新人 |

**定价规则**（`is_regular=1` 的常规价格）：

| category | 含义 | base_price(分) | base_price(元) |
|----------|------|---------------|---------------|
| 1 | 局视频 | 1000 | 10 |
| 30 | 单杆 30+ | 300 | 3 |
| 40 | 单杆 40+ | 400 | 4 |
| 50 | 单杆 50+ | 500 | 5 |
| 60 | 单杆 60+ | 600 | 6 |
| 70 | 单杆 70+ | 700 | 7 |
| 80 | 单杆 80+ | 800 | 8 |
| 90 | 单杆 90+ | 900 | 9 |
| 100 | 单杆 100+ | 1000 | 10 |
| 110 | 单杆 110+ | 1200 | 12 |
| 120 | 单杆 120+ | 1400 | 14 |
| 130 | 单杆 130+ | 1600 | 16 |
| 140 | 单杆 140+ | 1800 | 18 |

**折扣规则**：

| discount 值 | 含义 |
|------------|------|
| 10 | **1 折**（原价的 10%） |
| 20 | 2 折 |
| 30 | 3 折 |
| 40 | 4 折 |
| 50 | 5 折 |
| 70 | 7 折 |
| 85 | 85 折 |
| 90 | 9 折 |

> **🔴 重要修正**：`discount=10` 表示 **1 折**（原价的 10%），不是 9 折！折扣值直接代表折后百分比。

### 2.8 video_refund — 视频退款表（68 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 自增主键 |
| create_time | datetime | 创建时间 |
| wx_orderid | varchar(100) | 传给微信的订单编号 |
| transaction_id | varchar(40) | 微信支付订单号 |
| combo_order_id | bigint | 套餐订单号 |
| out_refund_no | varchar(40) | 退款单号 |
| **status** | int | **状态**：0=待审核, 1=审核通过, 2=退款成功, 3=退款失败, 4=初审不通过 |
| auditor | varchar(255) | 审核人 |
| auditTime | datetime | 审核时间 |
| wx_refund_time | datetime | 微信退款回调时间 |
| wx_refund_result | varchar(1000) | 微信回调返回内容 |
| remark | varchar(255) | 备注 |
| amount | int | 退款额（分） |
| user_id | varchar(36) | 提交退款的用户 ID |
| order_id | bigint | 对应视频订单 ID |
| wx_notify_result | varchar(1000) | 退款通知接口收到的返回内容 |

### 2.9 video_source — 视频原片表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键，原片 ID |
| **order_id** | bigint | **视频 ID（video_list 的 ID）** |
| create_time | datetime | 创建时间 |
| **url_video** | varchar(400) | **视频地址**（腾讯云原片 URL） |
| **url_bin** | varchar(400) | **bin 地址** |

> **⚠️ 注意**：`order_id` 字段注释写的是"视频 ID video_list 的 ID"，而非订单 ID。该表存储工控机上传的原始视频片段地址，是 App 本地制作的源头。

### 2.10 video_client_status — 客户端视频状态表 🔴

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint unsigned | 自增主键 |
| video_id | bigint unsigned | 视频 ID（video_list 的 ID） |
| **client_id** | varchar(64) | **客户端唯一标识（手机设备的 UDID）** |
| **status** | tinyint unsigned | **客户端视频状态**（见下表） |
| created_at / updated_at | datetime | 创建/更新时间 |

#### video_client_status.status 完整状态机

| 值 | 状态 | 说明 | 小程序同步文案 |
|----|------|------|---------------|
| 0 | **待解锁** | 视频已创建，等待用户解锁/付费 | 未明确 |
| 1 | **已解锁等待上传** | 用户已解锁，等待工控机上传原片到腾讯云 | 制作中，请至App内查看 |
| 2 | 原片已上传 | 工控机已上传原片到腾讯云 | 未明确 |
| 3 | **下载中** | App 正在从腾讯云下载原片 | 制作中，请至App内查看 |
| 4 | **下载失败** | 原片下载失败（网络/文件丢失） | 制作失败，请至App内查看 |
| 5 | **本地制作中** | App 正在本地制作视频（叠加比分条、头像等） | 制作中，请至App内查看 |
| 6 | **制作失败** | 本地制作失败（素材丢失/App 不在前台） | 制作失败，请至App内查看 |
| 7 | **制作完成** | 成品视频已生成，可播放 | 制作成功，请至App内查看 |
| 8 | 已过期 | 视频已过期 | 已过期 |
| 9 | **重新制作** | APP端新增状态 | 未明确（小程序端无对应状态） |

> **⚠️ 状态体系不统一**：APP 端 `video_client_status.status` 有 10 种（0~9），小程序端 `video_list.status` 只有 3 种（0=待剪辑, 1=已购买, 2=已删除），订单端 `video_order.video_status` 只有 2 种（1=工控机已生成, 2=工控机未合成）。三套状态枚举完全不同，是 APP↔小程序状态同步问题的根源。

> **⚠️ 数据库实际缺失**：status=0(待解锁)、1(已解锁等待上传)、8(已过期) 的记录在数据库中不存在，实际只有 2/3/4/5/6/7/9。

### 2.11 video_event — 视频播放事件表（138 条，埋点）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 自增主键，事件 ID |
| **type** | tinyint | **事件类型**：1=播放 |
| **from_type** | tinyint | **事件来源**：1=工控机, 2=小程序 |
| **from_device** | varchar(128) | **事件来源设备**：工控机=devicesn, 小程序=userId |
| video_id | bigint | 视频来源 ID |
| event_time | datetime | 事件时间 |
| play_count | int | 播放次数 |
| play_ms | bigint | 播放时长（ms） |
| create_time | datetime | 创建时间 |

> **⚠️ 注意**：当前 `from_type` 只有 1（工控机）和 2（小程序），**缺少 App 端的来源值（3）**。国内 App 的埋点需要新增 `from_type=3`。

### 2.12 video_promotion — 视频促销活动表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键，活动 ID |
| start_time / end_time | datetime | 促销活动开始/结束时间 |
| **discount** | int | **折扣，一折就写 10，85 折就写 85** |
| status | int | 1=正常，其他值=停止 |

> **确认**：`discount=10` = 1 折，`discount=85` = 85 折。折扣值 = 折后百分比。

### 2.13 pay_order — 支付订单表（535 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键 |
| amount | int | 金额（单位：分） |
| **channel** | tinyint | **类型**：0=同个人账户间转账, 1=微信支付 |
| csm_group_id / csm_type / csm_user_id | int/tinyint/varchar | 付款方信息 |
| mch_group_id / mch_type / mch_user_id | int/tinyint/varchar | 收款方信息 |
| pay_order_no | varchar(36) | 支付订单号 |
| pay_wx_order_no | varchar(36) | 微信单号 |
| remark | varchar(255) | 备注 |
| **status** | tinyint | **状态**：0=预创建订单, 1=已支付, 2=退款成功, 3=退款中, 4=退款成功, 5=退款失败, 6=扣款失败, 7=超时 |
| time_expire / time_pay / time_start | datetime | 过期/支付/开始时间 |
| name | varchar(255) | 商品名 |

### 2.14 pay_cash_order — 现金支付订单表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 自增主键 |
| amount | int | 支付现金金额（分） |
| balance | int | 余额 |
| cash_order_no | varchar(36) | 支付订单号 |
| cash_wx_order_no | varchar(36) | 传给微信订单号 |
| remark | varchar(255) | 备注 |
| **status** | tinyint | **订单状态**：0=待支付, 1=等待退款, 2=退款成功, 3=退款失败 |
| **audit** | tinyint | **审核状态**：-1=未审核, 0=拒绝, 1=通过, 2=审核失败 |
| time_expire / time_start | datetime | 过期/开始时间 |
| user_id | varchar(255) | 用户 UnionID |
| nickname | varchar(255) | 微信昵称 |
| open_id | varchar(255) | 用户 OpenID |
| merchant_address_id | varchar(36) | 商户 ID |

### 2.15 pay_refund — 支付退款表

| 字段 | 类型 | 说明 |
|------|------|------|
| （当前 0 条记录） | — | — |

---

## 三、用户数据关联规则

**查询路径**：手机号 → ten_user.id → ten_inning.left_id/right_id → 比赛数据

| 表名 | 说明 | 关联方式 |
|------|------|---------|
| ten_user | 用户基础信息 | 主表，phone/union_id 查询 |
| ten_inning | 局记录 | left_id / right_id 匹配 user_id |
| ten_score | 得分记录（聚合） | user_id 直接关联 |
| video_order | 视频订单 | user_id 直接关联 |
| video_list | 视频列表 | merchant_address_id 关联俱乐部 |
| video_combo_order | 套餐订单 | user_id 直接关联 |
| video_coupon_record | 视频券 | user_id 直接关联 |

**⚠️ 无数据的表**（斯诺克模式）：
- `ten_hit_info`: 击球信息表无记录（可能工控机未上传详细击球数据）
- `ten_participants`: 参赛人表无记录（斯诺克通过 ten_inning 的 left_id/right_id 直接关联）

### 3.1 关键关系图

```
ten_user (用户)
    │ user_id
    ├──→ video_order (谁买了哪个视频)   ← 按 user_id 区分购买者
    │       │ video_id
    │       ▼
    │   video_list (全场视频目录)        ← 一个 video_id 只有一条，不区分用户
    │       │ competition_id
    │       ▼
    └──→ ten_inning (用户参与的局)       ← left_id / right_id 匹配
            │ competition_id
            └──→ video_list (该场所有视频)

video_client_status (设备端状态)         ← 按 client_id(设备UDID) 区分
    video_id + client_id → 唯一标识某设备上某视频的状态
```

---

## 四、国内 App 业务数据流分析

### 4.1 视频解锁流程

```
用户点击解锁视频
    │
    ├── 用券解锁 → video_coupon_record.status 更新 (0→1)
    │                  ↓
    │              video_order 创建记录 (pay_status=支付成功)
    │                  ↓
    │              通知工控机上传原片 → video_source 插入记录
    │              video_client_status 更新 (0→1→2)
    │
    └── 付费解锁 → pay_order 创建支付订单 (status=0 预创建)
                       ↓
                   微信支付/IAP 支付
                       ↓
                   pay_order 更新 (status=1 已支付)
                   video_order 更新 (pay_status=支付成功)
                       ↓
                   通知工控机上传原片 → video_source 插入记录
```

### 4.2 视频制作完整状态流转

```
video_client_status.status 完整状态机:

  0 (待解锁)
    ↓ 用户解锁/付费
  1 (已解锁等待上传)
    ↓ 工控机上传原片
  2 (原片已上传)
    ↓ App 开始下载原片
  3 (下载中)
    ├→ 5 (本地制作中) ← 下载成功
    └→ 4 (下载失败) ← 下载失败
  5 (本地制作中)
    ├→ 7 (制作完成) ← 正常完成
    └→ 6 (制作失败) ← 失败
  8 (已过期) ← 任何阶段超时（48h/90d/缓存清除）
  9 (重新制作) ← APP端新增状态
```

### 4.3 支付渠道区分

```
video_order.pay_channel:
  0 = 小程序 android
  1 = 小程序 ios
  2 = app_android       ← 国内 App 安卓端应写入此值
  3 = app_ios           ← 国内 App iOS 端应写入此值

video_combo_order.pay_channel:
  0 = android
  1 = ios
  ⚠️ 只有两个值，与 video_order 不一致

video_combo_order.channel:
  2 = H5
  其他值 = 小程序
  ⚠️ 没有 App 的渠道值，需后端新增

pay_order.channel:
  0 = 同个人账户间转账
  1 = 微信支付
  ️ 没有 IAP 支付渠道值，需后端新增
```

**⚠️ 测试关注点**：
- App 端购买记录应正确写入 `video_order.pay_channel=2`（android）或 `3`（ios）
- `video_combo_order.channel` 和 `pay_order.channel` 缺少 App 渠道值
- 后台筛选"购买渠道"功能依赖 `video_order.pay_channel` 字段
- 历史数据均为 `pay_channel=0` 或 `1`（小程序）

### 4.4 折扣规则

```
video_price.discount / video_promotion.discount:
  10 = 1 折（原价的 10%）
  20 = 2 折
  50 = 5 折
  85 = 85 折
  90 = 9 折

规则：discount 值 = 折后百分比，不是折扣幅度
```

---

## 五、关键发现与风险点总结

### 5.1 🔴 折扣理解错误（已修正）

| 项目 | 详情 |
|------|------|
| **问题** | 文档曾将 `discount=10` 误写为"9 折" |
| **实际** | `discount=10` = **1 折**（原价的 10%），discount 值 = 折后百分比 |
| **影响** | 测试用例中的价格计算逻辑需要修正 |

### 5.2 🔴 video_client_status 完整状态机

| 项目 | 详情 |
|------|------|
| **发现** | `video_client_status.status` 有 10 个状态值（0~9） |
| **意义** | 这是 App 本地制作的核心状态跟踪表 |
| **建议** | 测试用例应覆盖完整状态流转：0→1→2→3→5→7（正常）、3→4（下载失败）、5→6（制作失败） |

### 5.3 🟡 video_event 缺少 App 来源值

| 项目 | 详情 |
|------|------|
| **问题** | `from_type` 只有 1（工控机）和 2（小程序） |
| **影响** | App 端播放埋点无法区分来源 |
| **建议** | 后端新增 `from_type=3` 表示 App 端 |

### 5.4 🟡 video_combo_order.channel 缺少 App 值

| 项目 | 详情 |
|------|------|
| **问题** | `channel` 字段注释为"2=H5, 其他值=小程序"，没有 App 值 |
| **影响** | App 端购买视频券的渠道记录不准确 |
| **建议** | 后端新增渠道值表示 App |

### 5.5 🟡 视频券套餐价格数据异常

| 项目 | 详情 |
|------|------|
| **问题** | video_combo 表中 price 字段值为 100/101/102 分（约 1 元） |
| **预期** | PRD 文档要求 9.9 元/29.9 元/118.8 元 |
| **建议** | 确认是测试环境数据还是字段含义不同 |

### 5.6 🟢 定价规则完整

| 项目 | 详情 |
|------|------|
| **发现** | video_price 表包含所有单杆分数段的定价规则 |
| **覆盖** | 局视频 + 单杆 30+~140+ 共 13 个分类，与 PRD 一致 |

### 5.7  其他已知数据问题

| 问题 | 详情 |
|------|------|
| video_combo.price | 值为100/101/102分，与PRD的9.9/29.9/118.8元不符 |
| video_order.video_status | 大量为0，与注释（1=已生成,2=未合成）不一致；实际只有 0 和 2 两个值 |
| video_event.from_type | 只有2，缺工控机的1和App的3（App开发中） |
| discount=10 | 是1折非9折（折后百分比） |
| **三套状态体系不统一** | APP端`video_client_status`有10种(0~9)，小程序端`video_list`只有3种(0/1/2)，订单端`video_order`只有2种(0/2)。同一视频在不同表状态不同，是APP↔小程序状态同步问题的根源 |
| **video_list 缺少细粒度状态** | 小程序无法区分制作中/制作失败/已过期/重新制作，所有已购买视频统一显示 status=1 |
| **video_client_status 缺失 0/1/8** | 数据库中无 status=0(待解锁)、1(已解锁等待上传)、8(已过期) 的记录，实际只有 2/3/4/5/6/7/9 |
| **status=9 重新制作** | 数据库有注释和10条数据，但小程序端无对应状态，APP↔小程序同步时可能丢失 |

---

## 六、数据库与测试点对应关系

| 测试点模块 | 相关数据库表 | 关键验证字段 |
|-----------|-------------|-------------|
| 视频解锁 | video_order, video_list | pay_status, video_status, amount |
| 视频券购买 | video_combo, video_combo_order, video_coupon_record | price, video_count, end_time, status |
| 付费解锁 | video_order, pay_order | pay_channel, amount, pay_status |
| 视频定价 | video_price | category, base_price, discount, is_regular |
| 退款 | video_refund, video_order | status(0~4), refund_status(0~3) |
| 视频制作状态 | video_client_status, video_source | status(0~9), url_video |
| 播放埋点 | video_event | type, from_type, play_count, play_ms |
| 后台渠道筛选 | video_order, video_combo_order | pay_channel, channel |
| 促销活动 | video_promotion | discount(10=1折), status |

---

## 七、测试用户数据速查

> 用于排查日志及数据库，快速定位用户、场、视频的关系
> 最后更新：2026-08-27

### 7.1 用户基本信息

| 项目 | 用户A（ice） | 用户B（Natural） | 用户C |
|------|-------------|-----------------|-------|
| **手机号** | 17620885381 | 13538506002 | 19928710361 |
| **user_id** | `aff7eae4-3680-4b89-9f01-819e02c3b6b5` | `57d703dc-659a-4474-898e-b75efa1f2e0a` | `1ad5d8c9-2a67-4f6b-93e9-e75f979e2e39` |
| **union_id** | `oIp-Q5pI-MlZ2Lov0zX-cIhs4caw` | `oIp-Q5uHh1HHD4UBBSr51Y2b_0KE` | `oIp-Q5qUwi6ULEGjTchV6FRL3xhc` |

### 7.2 比赛场次与视频关系

#### 共同场次（两人都在场中，competition_id 相同）

| competition_id | video_list 视频数 | ice 解锁 | Natural 解锁 | 备注 |
|---------------|------------------|---------|-------------|------|
| `fecd7c799ea5495ca23caceafaaca04b` | 3条 | ✅ 12001, 12002 | ✅ 12001 | video_id=12001 两人都买过 |
| `db6de10dea6a4c77ae9bde2d07c428b6` | 6条 | ❌ | ✅ 12387/12388/12391/12392/12393/12394 | Natural App安卓端解锁，全部制作完成 |
| `94acb2c4f2ac4d64b1ee641f7e1d3175` | 4条 | ❌ | ✅ 12375/12376/12377/12378 | 全部制作完成 |
| `29af92ac85bf451cb3e4bb45f58a4560` | 4条 |  | ✅ 12323/12324/12325/12326 | 全部制作完成 |
| `68715045f175472288c24c858b9da6e4` | 3条 | ❌ | ✅ 12180/12181(小程序) + 12182(App) | **12182 制作失败** |
| `0b9a4e7c4c3b45cf9612c5e6c587971c` | 1条 |  | ✅ 12021 | — |

#### ice 单独场次

| competition_id | 视频数 | 状态 |
|---------------|--------|------|
| `fecd7c799ea5495ca23caceafaaca04b` | 3条 | 12001/12002 已购买（小程序），1条视频两人均解锁 |

#### Natural 单独场次（小程序时期解锁）

| competition_id | 视频数 | 解锁渠道 | 备注 |
|---------------|--------|---------|------|
| `bfda6bbee4aa42a98d061c65909e035f` | 2 | 小程序 | — |
| `519c3a04995c41e1a7e0cece4aa18344` | 3 | 小程序 | 含单杆20+(27分) |
| `96a58c8363f64b39ad39e725dfaeab6b` | 3 | 小程序 | — |
| `44422073d17f41f794e672c82e13aeb1` | 5 | 小程序 | 含单杆20+(27分) |
| `4ad73acf067045b484c5177f933e564b` | 2 | 小程序 | — |
| `b9832083149348d9943978a68e536840` | 5 | 小程序 | — |
| `7e6a253cf84545b08687502c8813a8d3` | 3 | 小程序 | — |

#### ice 未解锁场次（video_list 有待解锁视频，但 user 无 video_order 记录）

| competition_id | 视频数 | 类型 |
|---------------|--------|------|
| `10aaa8bd` | 8 | 局×4 + 失败×2 + 精彩×2 |
| `d5fbeae5` | 4 | 局×4 |
| `40157a50` | 12 | 局×8 + 失败×2 + 单杆20+×2 |
| `b2208e66` | 6 | 局×6 |
| `dc209a18` | 12 | 局×4 + 失败×2 + 单杆20+×4 |
| `bee0e6ae` | 4 | 局×4 |
| `73dc910b` | 4 | 局×4 |
| `baad59a0` | 6 | 局×4 + 单杆20+×2 |

### 7.3 App 端制作状态（video_client_status）

#### Natural 设备（client_id: `2d14c8a0-66c6-4f04...`）

| video_id | 状态 | 更新时间 | 所属场 |
|----------|------|---------|-------|
| 12391 | 制作完成 | 08-21 17:05 | db6de10d |
| 12392 | 制作完成 | 08-21 17:01 | db6de10d |
| 12387 | 制作完成 | 08-21 17:00 | db6de10d |
| 12388 | 制作完成 | 08-21 17:04 | db6de10d |
| 12393 | 制作完成 | 08-21 17:08 | db6de10d |
| 12394 | 制作完成 | 08-21 17:07 | db6de10d |
| 12375 | 制作完成 | 08-21 17:13 | 94acb2c4 |
| 12376 | 制作完成 | 08-21 17:14 | 94acb2c4 |
| 12377 | 制作完成 | 08-21 17:12 | 94acb2c4 |
| 12378 | 制作完成 | 08-21 17:12 | 94acb2c4 |
| 12323 | 制作完成 | 08-21 17:04 | 29af92ac |
| 12324 | 制作完成 | 08-21 17:12 | 29af92ac |
| 12325 | 制作完成 | 08-21 17:00 | 29af92ac |
| 12326 | 制作完成 | 08-21 17:00 | 29af92ac |
| **12182** | **制作失败** | 08-21 16:37 | 68715045 |

#### Natural 旧设备（client_id: `2149f99f-3c66-42d7...`，08-20 使用）

| video_id | 状态 | 更新时间 |
|----------|------|---------|
| 12323 | 制作完成 | 08-20 22:48 |
| 12324 | 制作完成 | 08-20 22:52 |
| 12325 | 制作完成 | 08-20 21:53 |
| 12326 | 制作完成 | 08-20 21:52 |
| 12182 | 制作失败 | 08-20 14:34 |

---

## 八、视频业务SQL查询大全

> 所有SQL可直接在DBeaver中执行，`{user_id}` / `{video_id}` 等占位符替换为实际值

### 8.1 用户维度查询

#### 查询用户基本信息
```sql
SELECT id, nickname, union_id, create_time
FROM ten_user
WHERE id = '{user_id}';
```

#### 通过UnionID查用户
```sql
SELECT id, nickname, union_id, create_time
FROM ten_user
WHERE union_id = '{union_id}';
```

#### 用户视频资产汇总
```sql
SELECT
    u.id AS user_id,
    u.nickname,
    COUNT(DISTINCT vo.id) AS total_orders,
    SUM(CASE WHEN vo.pay_status = '支付成功' THEN 1 ELSE 0 END) AS paid_orders,
    SUM(CASE WHEN vo.pay_status = '待支付' THEN 1 ELSE 0 END) AS unpaid_orders,
    COUNT(DISTINCT vcr.id) AS total_coupons,
    SUM(CASE WHEN vcr.status = 0 THEN 1 ELSE 0 END) AS valid_coupons,
    SUM(CASE WHEN vcr.status = 1 THEN 1 ELSE 0 END) AS used_coupons,
    SUM(CASE WHEN vcr.status = 2 THEN 1 ELSE 0 END) AS expired_coupons
FROM ten_user u
LEFT JOIN video_order vo ON u.id = vo.user_id
LEFT JOIN video_coupon_record vcr ON u.id = vcr.user_id
WHERE u.id = '{user_id}'
GROUP BY u.id, u.nickname;
```

### 8.2 视频订单查询

#### 用户所有视频订单
```sql
SELECT vo.id, vo.video_id, vo.user_id, vo.union_id,
       vo.pay_status, vo.video_status, vo.amount,
       vo.left_play_times, vo.is_viewed, vo.view_time,
       vo.pay_channel, vo.refund_status,
       vo.create_time, vo.pay_time, vo.upload_time,
       vo.combo_order_id
FROM video_order vo
WHERE vo.user_id = '{user_id}'
ORDER BY vo.create_time DESC;
```

#### 按支付状态筛选
```sql
-- 已支付订单
SELECT * FROM video_order
WHERE user_id = '{user_id}' AND pay_status = '支付成功';

-- 待支付订单
SELECT * FROM video_order
WHERE user_id = '{user_id}' AND pay_status = '待支付';

-- 支付失败订单
SELECT * FROM video_order
WHERE user_id = '{user_id}' AND pay_status = '支付失败';
```

#### 按视频状态筛选
```sql
-- 待处理（video_status=0）
SELECT * FROM video_order WHERE video_status = 0;

-- 工控机已生成（video_status=1）
SELECT * FROM video_order WHERE video_status = 1;

-- 工控机未合成（video_status=2）
SELECT * FROM video_order WHERE video_status = 2;
```

#### 按退款状态筛选
```sql
-- refund_status: 0=未退款, 1=已申请退款, 2=已退款, 3=退款失败
SELECT * FROM video_order
WHERE refund_status = 1;  -- 已申请退款
```

#### 按支付渠道筛选
```sql
-- pay_channel: 0=小程序android, 1=小程序ios, 2=app_android, 3=app_ios
SELECT pay_channel, COUNT(*) AS cnt
FROM video_order
WHERE pay_status = '支付成功'
GROUP BY pay_channel;

-- App端购买记录
SELECT * FROM video_order
WHERE pay_channel IN (2, 3);
```

#### 用户未观看的视频
```sql
SELECT vo.id, vo.video_id, vo.amount, vo.create_time
FROM video_order vo
WHERE vo.user_id = '{user_id}'
  AND vo.pay_status = '支付成功'
  AND vo.is_viewed = 0;
```

#### 重复订单检测（同一用户同一视频多次购买）
```sql
SELECT user_id, video_id, COUNT(*) AS order_count
FROM video_order
WHERE pay_status = '支付成功'
GROUP BY user_id, video_id
HAVING COUNT(*) > 1;
```

### 8.3 视频券查询

#### 用户所有视频券
```sql
SELECT vcr.id, vcr.user_id, vcr.coupon_id,
       CASE vcr.coupon_id
           WHEN 1 THEN '套餐券'
           WHEN 2 THEN '活动券(7天打卡)'
           ELSE CONCAT('未知类型(', vcr.coupon_id, ')')
       END AS coupon_type,
       CASE vcr.status
           WHEN 0 THEN '有效'
           WHEN 1 THEN '已使用'
           WHEN 2 THEN '已过期'
       END AS status_text,
       vcr.draw_time, vcr.end_date, vcr.order_id
FROM video_coupon_record vcr
WHERE vcr.user_id = '{user_id}'
ORDER BY vcr.draw_time DESC;
```

#### 有效视频券数量
```sql
SELECT COUNT(*) AS valid_coupon_count
FROM video_coupon_record
WHERE user_id = '{user_id}' AND status = 0;
```

#### 即将过期的视频券（7天内）
```sql
SELECT vcr.*,
       TIMESTAMPDIFF(HOUR, NOW(), vcr.end_date) AS hours_left
FROM video_coupon_record vcr
WHERE vcr.user_id = '{user_id}'
  AND vcr.status = 0
  AND vcr.end_date BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY)
ORDER BY vcr.end_date;
```

#### 已过期但未更新状态的券
```sql
SELECT * FROM video_coupon_record
WHERE status = 0
  AND end_date < NOW();
```

#### 券使用关联追溯（券→订单→视频）
```sql
SELECT vcr.id AS coupon_id, vcr.coupon_id AS coupon_type,
       vo.id AS order_id, vo.video_id, vo.amount,
       vo.pay_status, vo.create_time
FROM video_coupon_record vcr
LEFT JOIN video_order vo ON vcr.order_id = vo.id
WHERE vcr.user_id = '{user_id}'
ORDER BY vcr.draw_time DESC;
```

### 8.4 套餐订单查询

#### 用户套餐订单
```sql
SELECT vco.id, vco.combo_id, vco.video_count, vco.used_count,
       vco.pay_status, vco.end_time, vco.channel, vco.pay_channel,
       vco.refund_status, vco.create_time, vco.pay_time
FROM video_combo_order vco
WHERE vco.user_id = '{user_id}'
ORDER BY vco.create_time DESC;
```

#### 套餐定义（当前可用的套餐）
```sql
SELECT id, price/100 AS price_yuan, video_count,
       single_price/100 AS single_price_yuan,
       save_money/100 AS save_money_yuan,
       month AS valid_months, status
FROM video_combo
WHERE status = 1
ORDER BY display_order;
```

#### 套餐使用率统计
```sql
SELECT vco.id, vco.combo_id, vc.price/100 AS price_yuan,
       vco.video_count, vco.used_count,
       ROUND(vco.used_count / vco.video_count * 100, 1) AS usage_pct,
       vco.end_time, vco.create_time
FROM video_combo_order vco
LEFT JOIN video_combo vc ON vco.combo_id = vc.id
WHERE vco.user_id = '{user_id}'
  AND vco.pay_status = '支付成功';
```

#### 未支付的套餐订单
```sql
SELECT * FROM video_combo_order
WHERE pay_status IS NULL OR pay_status = '支付失败';
```

#### 已过期的套餐订单
```sql
SELECT * FROM video_combo_order
WHERE end_time IS NOT NULL
  AND end_time < NOW()
  AND pay_status = '支付成功';
```

### 8.5 视频制作状态查询（核心）

#### 完整状态机流转查询
```sql
-- video_client_status: 0=待解锁, 1=已解锁等待上传, 2=原片已上传,
--   3=下载中, 4=下载失败, 5=本地制作中, 6=制作失败, 7=制作完成, 8=已过期, 9=重新制作
SELECT vcs.video_id,
       CASE vcs.status
           WHEN 0 THEN '待解锁'
           WHEN 1 THEN '已解锁等待上传'
           WHEN 2 THEN '原片已上传'
           WHEN 3 THEN '下载中'
           WHEN 4 THEN '下载失败'
           WHEN 5 THEN '本地制作中'
           WHEN 6 THEN '制作失败'
           WHEN 7 THEN '制作完成'
           WHEN 8 THEN '已过期'
           WHEN 9 THEN '重新制作'
       END AS status_text,
       vcs.client_id, vcs.created_at, vcs.updated_at,
       TIMESTAMPDIFF(MINUTE, vcs.created_at, vcs.updated_at) AS process_minutes
FROM video_client_status vcs
JOIN video_order vo ON vcs.video_id = vo.video_id
WHERE vo.user_id = '{user_id}'
ORDER BY vcs.updated_at DESC;
```

#### 各状态视频数量统计
```sql
SELECT
    CASE vcs.status
        WHEN 0 THEN '待解锁' WHEN 1 THEN '已解锁等待上传'
        WHEN 2 THEN '原片已上传' WHEN 3 THEN '下载中'
        WHEN 4 THEN '下载失败' WHEN 5 THEN '本地制作中'
        WHEN 6 THEN '制作失败' WHEN 7 THEN '制作完成'
        WHEN 8 THEN '已过期' WHEN 9 THEN '重新制作'
    END AS status_text,
    COUNT(*) AS video_count
FROM video_client_status vcs
GROUP BY vcs.status
ORDER BY vcs.status;
```

#### 下载失败视频
```sql
SELECT vcs.video_id, vcs.client_id, vcs.updated_at,
       vo.video_id, vo.amount, vo.create_time
FROM video_client_status vcs
JOIN video_order vo ON vcs.video_id = vo.video_id
WHERE vcs.status = 4
ORDER BY vcs.updated_at DESC;
```

#### 制作失败视频
```sql
SELECT vcs.video_id, vcs.client_id, vcs.updated_at,
       vo.amount, vo.create_time
FROM video_client_status vcs
JOIN video_order vo ON vcs.video_id = vo.video_id
WHERE vcs.status = 6
ORDER BY vcs.updated_at DESC;
```

#### 正在制作中的视频（下载中+本地制作中）
```sql
SELECT vcs.video_id,
       CASE vcs.status WHEN 3 THEN '下载中' WHEN 5 THEN '本地制作中' END AS making_status,
       vcs.client_id, vcs.updated_at
FROM video_client_status vcs
WHERE vcs.status IN (3, 5)
ORDER BY vcs.updated_at DESC;
```

#### 同一设备（client_id）的所有视频状态
```sql
SELECT vcs.video_id, vcs.status, vcs.client_id,
       vcs.created_at, vcs.updated_at
FROM video_client_status vcs
WHERE vcs.client_id = '{device_udid}'
ORDER BY vcs.updated_at DESC;
```

#### 状态流转耗时分析
```sql
-- 从解锁到制作完成的总耗时
SELECT vcs.video_id,
       MIN(CASE WHEN vcs.status = 1 THEN vcs.updated_at END) AS unlock_time,
       MAX(CASE WHEN vcs.status = 7 THEN vcs.updated_at END) AS complete_time,
       TIMESTAMPDIFF(MINUTE,
           MIN(CASE WHEN vcs.status = 1 THEN vcs.updated_at END),
           MAX(CASE WHEN vcs.status = 7 THEN vcs.updated_at END)
       ) AS total_minutes
FROM video_client_status vcs
WHERE vcs.video_id IN (SELECT video_id FROM video_order WHERE user_id = '{user_id}')
GROUP BY vcs.video_id;
```

### 8.6 视频原片查询

#### 用户视频的原片地址
```sql
SELECT vs.id, vs.order_id AS video_id,
       vs.url_video, vs.url_bin, vs.create_time
FROM video_source vs
JOIN video_order vo ON vs.order_id = vo.video_id
WHERE vo.user_id = '{user_id}'
ORDER BY vs.create_time DESC;
```

#### 未上传原片的已解锁视频
```sql
SELECT vo.id, vo.video_id, vo.user_id, vo.pay_status, vo.create_time
FROM video_order vo
LEFT JOIN video_source vs ON vo.video_id = vs.order_id
WHERE vo.user_id = '{user_id}'
  AND vo.pay_status = '支付成功'
  AND vs.id IS NULL;
```

### 8.7 视频目录查询

#### 视频详情（根据video_id）
```sql
SELECT vl.id, vl.competition_id, vl.inning_id, vl.frame_index,
       vl.category, vl.content, vl.price/100 AS price_yuan,
       vl.duration, vl.nickname_a, vl.nickname_b,
       vl.buy_times, vl.amount/100 AS amount_yuan,
       vl.status, vl.last_pay_time, vl.player,
       vl.break_score, vl.flag
FROM video_list vl
WHERE vl.id = {video_id};
```

#### 按分类查询视频
```sql
-- category: 单杆20+/单杆30+/单杆50+/单杆80+/单杆破百/局视频/进攻失败合集/长台精彩集锦
SELECT category, COUNT(*) AS cnt,
       SUM(buy_times) AS total_buys,
       SUM(amount)/100 AS total_revenue_yuan
FROM video_list
GROUP BY category
ORDER BY total_revenue_yuan DESC;
```

#### 用户解锁的视频列表（含视频元信息）
```sql
SELECT vo.video_id, vl.category, vl.content, vl.nickname_a, vl.nickname_b,
       vl.duration, vl.break_score, vl.price/100 AS price_yuan,
       vo.pay_status, vo.amount/100 AS paid_yuan, vo.pay_time
FROM video_order vo
JOIN video_list vl ON vo.video_id = vl.id
WHERE vo.user_id = '{user_id}'
  AND vo.pay_status = '支付成功'
ORDER BY vo.pay_time DESC;
```

### 8.8 播放埋点查询

#### 用户播放事件
```sql
-- from_type: 1=工控机, 2=小程序, 3=App(新增)
SELECT ve.id, ve.type,
       CASE ve.from_type
           WHEN 1 THEN '工控机'
           WHEN 2 THEN '小程序'
           WHEN 3 THEN 'App'
       END AS source,
       ve.from_device, ve.video_id,
       ve.play_count, ve.play_ms/1000 AS play_seconds,
       ve.event_time, ve.create_time
FROM video_event ve
WHERE ve.from_device = '{user_id}'
ORDER BY ve.event_time DESC;
```

#### 视频播放统计
```sql
SELECT video_id,
       COUNT(*) AS play_times,
       SUM(play_count) AS total_plays,
       SUM(play_ms)/1000 AS total_play_seconds,
       MIN(event_time) AS first_play,
       MAX(event_time) AS last_play
FROM video_event
WHERE video_id = {video_id}
GROUP BY video_id;
```

#### 按来源类型统计播放量
```sql
SELECT
    CASE from_type
        WHEN 1 THEN '工控机'
        WHEN 2 THEN '小程序'
        WHEN 3 THEN 'App'
    END AS source,
    COUNT(*) AS event_count,
    SUM(play_count) AS total_plays
FROM video_event
GROUP BY from_type;
```

#### 热门视频排行（播放次数）
```sql
SELECT video_id, COUNT(*) AS play_count, SUM(play_ms)/1000 AS total_seconds
FROM video_event
GROUP BY video_id
ORDER BY play_count DESC
LIMIT 20;
```

### 8.9 退款查询

#### 用户退款记录
```sql
-- status: 0=待审核, 1=审核通过, 2=退款成功, 3=退款失败, 4=初审不通过
SELECT vr.id, vr.order_id, vr.combo_order_id,
       CASE vr.status
           WHEN 0 THEN '待审核' WHEN 1 THEN '审核通过'
           WHEN 2 THEN '退款成功' WHEN 3 THEN '退款失败'
           WHEN 4 THEN '初审不通过'
       END AS refund_status,
       vr.amount/100 AS refund_yuan,
       vr.auditor, vr.auditTime, vr.wx_refund_time,
       vr.create_time, vr.remark
FROM video_refund vr
WHERE vr.user_id = '{user_id}'
ORDER BY vr.create_time DESC;
```

#### 退款失败记录排查
```sql
SELECT vr.id, vr.order_id, vr.user_id, vr.amount,
       vr.status, vr.wx_refund_result, vr.wx_notify_result,
       vr.create_time
FROM video_refund vr
WHERE vr.status = 3  -- 退款失败
ORDER BY vr.create_time DESC;
```

#### 待审核退款
```sql
SELECT vr.id, vr.order_id, vr.user_id, vr.amount/100 AS amount_yuan,
       vo.video_id, vo.pay_status AS order_pay_status,
       vr.create_time
FROM video_refund vr
LEFT JOIN video_order vo ON vr.order_id = vo.id
WHERE vr.status = 0  -- 待审核
ORDER BY vr.create_time;
```

### 8.10 定价与促销查询

#### 视频定价规则（固定价格）
```sql
-- is_regular=1 为固定项目不可编辑
SELECT id,
       CASE category WHEN 1 THEN '局视频' ELSE CONCAT('单杆', category, '+') END AS category_name,
       base_price/100 AS base_price_yuan,
       discount_price/100 AS discount_price_yuan,
       discount AS discount_pct,  -- 10=1折, 50=5折
       latest_begin_time, latest_end_time,
       apply_times, is_regular
FROM video_price
WHERE is_regular = 1
ORDER BY category;
```

#### 当前生效的促销活动
```sql
-- discount: 10=1折, 85=85折
SELECT id, start_time, end_time, discount,
       CASE WHEN status = 1 THEN '正常' ELSE '停止' END AS activity_status,
       TIMESTAMPDIFF(HOUR, NOW(), end_time) AS hours_remaining
FROM video_promotion
WHERE status = 1 AND end_time > NOW()
ORDER BY discount;
```

#### 历史折扣记录
```sql
SELECT category, base_price/100, discount_price/100, discount,
       latest_begin_time, latest_end_time, apply_times,
       create_user, update_time, update_user
FROM video_price
WHERE category = {category_id}
ORDER BY latest_begin_time DESC;
```

### 8.11 支付订单查询

#### 用户支付订单
```sql
-- channel: 0=同个人账户间转账, 1=微信支付
-- status: 0=预创建, 1=已支付, 2=退款成功, 3=退款中, 4=退款成功, 5=退款失败, 6=扣款失败, 7=超时
SELECT po.id, po.amount/100 AS amount_yuan,
       CASE po.channel WHEN 0 THEN '转账' WHEN 1 THEN '微信支付' END AS pay_type,
       CASE po.status
           WHEN 0 THEN '预创建' WHEN 1 THEN '已支付'
           WHEN 2 THEN '退款成功' WHEN 3 THEN '退款中'
           WHEN 4 THEN '退款成功' WHEN 5 THEN '退款失败'
           WHEN 6 THEN '扣款失败' WHEN 7 THEN '超时'
       END AS status_text,
       po.pay_order_no, po.pay_wx_order_no, po.name,
       po.time_start, po.time_pay, po.time_expire
FROM pay_order po
WHERE po.csm_user_id = '{user_id}'
ORDER BY po.time_start DESC;
```

#### 支付订单与视频订单关联
```sql
SELECT po.pay_order_no, po.amount/100 AS amount_yuan, po.status AS pay_status,
       vo.id AS video_order_id, vo.video_id, vo.pay_status AS video_pay_status
FROM pay_order po
LEFT JOIN video_order vo ON po.pay_order_no = vo.wx_orderid
WHERE po.csm_user_id = '{user_id}'
ORDER BY po.time_start DESC;
```

### 8.12 跨表关联查询

#### 用户视频完整信息（订单+目录+状态+原片）
```sql
SELECT vo.id AS order_id, vo.video_id,
       vl.category, vl.content, vl.nickname_a, vl.nickname_b, vl.duration,
       vo.pay_status, vo.amount/100 AS paid_yuan, vo.video_status,
       vcs.status AS client_status,
       CASE vcs.status
           WHEN 0 THEN '待解锁' WHEN 1 THEN '已解锁等待上传'
           WHEN 2 THEN '原片已上传' WHEN 3 THEN '下载中'
           WHEN 4 THEN '下载失败' WHEN 5 THEN '本地制作中'
           WHEN 6 THEN '制作失败' WHEN 7 THEN '制作完成'
           WHEN 8 THEN '已过期' WHEN 9 THEN '重新制作'
       END AS client_status_text,
       vs.url_video AS source_url,
       vo.create_time, vo.pay_time
FROM video_order vo
LEFT JOIN video_list vl ON vo.video_id = vl.id
LEFT JOIN video_client_status vcs ON vo.video_id = vcs.video_id
LEFT JOIN video_source vs ON vo.video_id = vs.order_id
WHERE vo.user_id = '{user_id}'
ORDER BY vo.create_time DESC;
```

#### 视频全生命周期追踪
```sql
-- 一个视频从创建到完成的所有关键节点
SELECT
    vl.id AS video_id, vl.category, vl.content,
    vo.id AS order_id, vo.user_id, vo.pay_status, vo.pay_time,
    vcs.status AS client_status,
    CASE vcs.status
        WHEN 0 THEN '待解锁' WHEN 1 THEN '已解锁等待上传'
        WHEN 2 THEN '原片已上传' WHEN 3 THEN '下载中'
        WHEN 4 THEN '下载失败' WHEN 5 THEN '本地制作中'
        WHEN 6 THEN '制作失败' WHEN 7 THEN '制作完成'
        WHEN 8 THEN '已过期' WHEN 9 THEN '重新制作'
    END AS client_status_text,
    vcs.updated_at AS last_status_time,
    vs.url_video IS NOT NULL AS has_source,
    ve.play_count
FROM video_list vl
LEFT JOIN video_order vo ON vl.id = vo.video_id
LEFT JOIN video_client_status vcs ON vl.id = vcs.video_id
LEFT JOIN video_source vs ON vl.id = vs.order_id
LEFT JOIN (SELECT video_id, SUM(play_count) AS play_count FROM video_event GROUP BY video_id) ve ON vl.id = ve.video_id
WHERE vl.id = {video_id};
```

#### 套餐→券→使用 完整链路
```sql
SELECT vco.id AS combo_order_id, vco.combo_id, vc.price/100 AS combo_price_yuan,
       vco.video_count, vco.used_count, vco.pay_status,
       vcr.id AS coupon_id,
       CASE vcr.coupon_id WHEN 1 THEN '套餐券' WHEN 2 THEN '活动券' END AS coupon_type,
       CASE vcr.status WHEN 0 THEN '有效' WHEN 1 THEN '已使用' WHEN 2 THEN '已过期' END AS coupon_status,
       vcr.order_id AS used_order_id,
       vcr.draw_time, vcr.end_date
FROM video_combo_order vco
LEFT JOIN video_combo vc ON vco.combo_id = vc.id
LEFT JOIN video_coupon_record vcr ON vcr.user_id = vco.user_id
WHERE vco.user_id = '{user_id}'
ORDER BY vco.create_time DESC, vcr.draw_time DESC;
```

### 8.13 数据统计与报表

#### 全量视频业务数据概览
```sql
SELECT
    (SELECT COUNT(*) FROM video_list) AS total_videos,
    (SELECT COUNT(*) FROM video_order WHERE pay_status = '支付成功') AS paid_orders,
    (SELECT COUNT(*) FROM video_order WHERE pay_status = '待支付') AS unpaid_orders,
    (SELECT SUM(amount)/100 FROM video_order WHERE pay_status = '支付成功') AS total_revenue_yuan,
    (SELECT COUNT(*) FROM video_coupon_record WHERE status = 0) AS valid_coupons,
    (SELECT COUNT(*) FROM video_combo_order WHERE pay_status = '支付成功') AS paid_combo_orders,
    (SELECT COUNT(*) FROM video_refund WHERE status = 2) AS successful_refunds,
    (SELECT COUNT(*) FROM video_client_status WHERE status = 7) AS completed_videos,
    (SELECT COUNT(*) FROM video_event) AS total_play_events;
```

#### 各分类视频收入统计
```sql
SELECT vl.category,
       COUNT(DISTINCT vo.id) AS order_count,
       SUM(CASE WHEN vo.pay_status = '支付成功' THEN 1 ELSE 0 END) AS paid_count,
       SUM(CASE WHEN vo.pay_status = '支付成功' THEN vo.amount ELSE 0 END)/100 AS revenue_yuan
FROM video_list vl
LEFT JOIN video_order vo ON vl.id = vo.video_id
GROUP BY vl.category
ORDER BY revenue_yuan DESC;
```

#### 每日视频解锁趋势
```sql
SELECT DATE(create_time) AS date,
       COUNT(*) AS total_orders,
       SUM(CASE WHEN pay_status = '支付成功' THEN 1 ELSE 0 END) AS paid,
       SUM(CASE WHEN pay_status = '待支付' THEN 1 ELSE 0 END) AS unpaid,
       SUM(CASE WHEN pay_status = '支付成功' THEN amount ELSE 0 END)/100 AS revenue_yuan
FROM video_order
GROUP BY DATE(create_time)
ORDER BY date DESC
LIMIT 30;
```

#### App vs 小程序 购买渠道分布
```sql
SELECT
    CASE pay_channel
        WHEN 0 THEN '小程序-Android'
        WHEN 1 THEN '小程序-iOS'
        WHEN 2 THEN 'App-Android'
        WHEN 3 THEN 'App-iOS'
    END AS channel,
    COUNT(*) AS order_count,
    SUM(amount)/100 AS revenue_yuan
FROM video_order
WHERE pay_status = '支付成功'
GROUP BY pay_channel
ORDER BY order_count DESC;
```

#### 视频制作成功率
```sql
SELECT
    CASE status
        WHEN 0 THEN '待解锁' WHEN 1 THEN '等待上传'
        WHEN 2 THEN '原片已上传' WHEN 3 THEN '下载中'
        WHEN 4 THEN '下载失败' WHEN 5 THEN '制作中'
        WHEN 6 THEN '制作失败' WHEN 7 THEN '制作完成'
        WHEN 8 THEN '已过期' WHEN 9 THEN '重新制作'
    END AS status_text,
    COUNT(*) AS count,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM video_client_status) * 100, 1) AS pct
FROM video_client_status
GROUP BY status
ORDER BY status;
```

#### 视频播放Top排行
```sql
SELECT vl.id AS video_id, vl.category, vl.nickname_a, vl.nickname_b,
       COUNT(ve.id) AS play_events,
       SUM(ve.play_count) AS total_plays,
       SUM(ve.play_ms)/1000/60 AS total_minutes
FROM video_event ve
JOIN video_list vl ON ve.video_id = vl.id
GROUP BY ve.video_id
ORDER BY total_plays DESC
LIMIT 20;
```

### 8.14 问题排查SQL

#### 已支付但无原片的视频
```sql
SELECT vo.id, vo.video_id, vo.user_id, vo.pay_status, vo.create_time
FROM video_order vo
LEFT JOIN video_source vs ON vo.video_id = vs.order_id
WHERE vo.pay_status = '支付成功'
  AND vs.id IS NULL;
```

#### 状态不一致的视频（video_order与video_client_status不匹配）
```sql
SELECT vo.id, vo.video_id, vo.video_status AS order_status,
       vcs.status AS client_status
FROM video_order vo
LEFT JOIN video_client_status vcs ON vo.video_id = vcs.video_id
WHERE vo.video_status != 0  -- 已处理的订单
  AND (vcs.status IS NULL OR vcs.status = 0);  -- 但客户端状态异常
```

#### 有券但从未使用的用户
```sql
SELECT u.id, u.nickname,
       COUNT(vcr.id) AS total_coupons,
       SUM(CASE WHEN vcr.status = 0 THEN 1 ELSE 0 END) AS unused_coupons
FROM ten_user u
JOIN video_coupon_record vcr ON u.id = vcr.user_id
GROUP BY u.id, u.nickname
HAVING unused_coupons > 0
ORDER BY unused_coupons DESC
LIMIT 20;
```

#### 套餐已支付但券未到账
```sql
SELECT vco.id, vco.user_id, vco.combo_id, vco.video_count,
       vco.pay_status, vco.create_time,
       (SELECT COUNT(*) FROM video_coupon_record
        WHERE user_id = vco.user_id
        AND draw_time >= vco.create_time) AS coupons_after_purchase
FROM video_combo_order vco
WHERE vco.pay_status = '支付成功'
  AND vco.used_count = 0
ORDER BY vco.create_time DESC;
```

#### 视频过期但未更新状态
```sql
-- 超过48小时未解锁的视频
SELECT vo.id, vo.video_id, vo.user_id, vo.create_time,
       TIMESTAMPDIFF(HOUR, vo.create_time, NOW()) AS hours_since_create
FROM video_order vo
LEFT JOIN video_client_status vcs ON vo.video_id = vcs.video_id
WHERE vo.pay_status = '支付成功'
  AND (vcs.status = 0 OR vcs.status IS NULL)
  AND TIMESTAMPDIFF(HOUR, vo.create_time, NOW()) > 48;
```

---

## 附录：表结构快速参考

| 表名 | 记录数 | 核心用途 |
|------|--------|---------|
| video_list | 1,438 | 视频目录/元数据 |
| video_order | 1,004 | 视频解锁订单 |
| video_combo | 3 | 套餐定义 |
| video_combo_order | 2,484 | 套餐订单 |
| video_coupon_record | 377 | 视频券记录 |
| video_event | 138 | 播放事件埋点 |
| video_price | 60+ | 定价规则 |
| video_refund | 68 | 退款记录 |
| video_source | - | 原片地址 |
| video_client_status | - | 客户端状态（0~9 共 10 个状态） |
| video_promotion | - | 促销活动 |
| pay_order | 535 | 支付订单 |
| pay_refund | 0 | 支付退款 |
| pay_cash_order | - | 现金支付订单 |

### 关键字段速查

| 表 | 用户关联字段 | 状态字段 | 金额单位 |
|---|---|---|---|
| video_order | user_id | pay_status / video_status | 分 |
| video_coupon_record | user_id | status (0/1/2) | — |
| video_combo_order | user_id | pay_status | 分 |
| video_client_status | (通过video_order关联) | status (0~9) | — |
| video_event | from_device | from_type | — |
| video_refund | user_id | status (0~4) | 分 |
| pay_order | csm_user_id | status (0~7) | 分 |
