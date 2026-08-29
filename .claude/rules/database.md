# 数据库关键表

> 连接: 121.40.243.17:3306 (supervisions库)
> 账号: linjiakun / 密码: Ljk@123456

## 视频业务核心表

| 表名 | 核心用途 | 关键状态/字段 |
|------|---------|-------------|
| video_client_status | App视频状态跟踪 | status: 0~9 共10个状态 |
| video_list | 小程序视频列表 | status: 0=待剪辑, 1=已购买, 2=已删除（仅3种） |
| video_order | 视频解锁订单 | video_status: 0/2（注释1/2与实际不符）; pay_channel(0~3), refund_status(0~3) |
| video_source | 视频原片地址 | url_video(腾讯云URL) |
| video_coupon_record | 视频券记录 | status: 0=有效, 1=已使用, 2=已过期 |
| video_event | 播放事件埋点 | from_type: 1=工控机, 2=小程序, 3=App |
| video_price | 定价规则 | discount(10=1折, 85=85折) |

## video_client_status 状态机（核心）

| 值 | 状态 | 小程序同步文案 |
|----|------|-------------|
| 0 | 待解锁 | 未明确（推测沿用现有样式） |
| 1 | 已解锁等待上传 | **制作中，请至App内查看** |
| 2 | 原片已上传 | 未明确（推测沿用现有样式） |
| 3 | 下载中 | 制作中，请至App内查看 |
| 4 | 下载失败 | 制作失败，请至App内查看 |
| 5 | 本地制作中 | 制作中，请至App内查看 |
| 6 | 制作失败 | 制作失败，请至App内查看 |
| 7 | 制作完成 | 制作成功，请至App内查看 |
| 8 | 已过期 | 已过期 |
| 9 | 重新制作 | 未明确（APP端新增状态，文档待补充） |

> ⚠️ **状态体系不统一**：APP 端 `video_client_status.status` 有 10 种（0~9），小程序端 `video_list.status` 只有 3 种（0=待剪辑, 1=已购买, 2=已删除），订单端 `video_order.video_status` 只有 2 种（1=工控机已生成, 2=工控机未合成）。三套状态枚举完全不同，是 APP↔小程序状态同步问题的根源。

## 用户数据关联规则

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

## 已知数据问题

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
