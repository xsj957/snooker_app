# 斯诺克大师国内App — 视频业务SQL查询大全

> **数据库**: supervisions（121.40.243.17:3306 / linjiakun）  
> **生成日期**: 2026-07-29  
> **说明**: 所有SQL可直接在DBeaver中执行，`{user_id}` / `{video_id}` 等占位符替换为实际值

---

## 一、用户维度查询

### 1.1 查询用户基本信息
```sql
SELECT id, nickname, union_id, create_time 
FROM ten_user 
WHERE id = '{user_id}';
```

### 1.2 通过UnionID查用户
```sql
SELECT id, nickname, union_id, create_time 
FROM ten_user 
WHERE union_id = '{union_id}';
```

### 1.3 用户视频资产汇总
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

---

## 二、视频订单查询

### 2.1 用户所有视频订单
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

### 2.2 按支付状态筛选
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

### 2.3 按视频状态筛选
```sql
-- 待处理（video_status=0）
SELECT * FROM video_order WHERE video_status = 0;

-- 工控机已生成（video_status=1）
SELECT * FROM video_order WHERE video_status = 1;

-- 工控机未合成（video_status=2）
SELECT * FROM video_order WHERE video_status = 2;
```

### 2.4 按退款状态筛选
```sql
-- refund_status: 0=未退款, 1=已申请退款, 2=已退款, 3=退款失败
SELECT * FROM video_order 
WHERE refund_status = 1;  -- 已申请退款
```

### 2.5 按支付渠道筛选
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

### 2.6 用户未观看的视频
```sql
SELECT vo.id, vo.video_id, vo.amount, vo.create_time
FROM video_order vo
WHERE vo.user_id = '{user_id}' 
  AND vo.pay_status = '支付成功'
  AND vo.is_viewed = 0;
```

### 2.7 重复订单检测（同一用户同一视频多次购买）
```sql
SELECT user_id, video_id, COUNT(*) AS order_count
FROM video_order
WHERE pay_status = '支付成功'
GROUP BY user_id, video_id
HAVING COUNT(*) > 1;
```

---

## 三、视频券查询

### 3.1 用户所有视频券
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

### 3.2 有效视频券数量
```sql
SELECT COUNT(*) AS valid_coupon_count
FROM video_coupon_record
WHERE user_id = '{user_id}' AND status = 0;
```

### 3.3 即将过期的视频券（7天内）
```sql
SELECT vcr.*, 
       TIMESTAMPDIFF(HOUR, NOW(), vcr.end_date) AS hours_left
FROM video_coupon_record vcr
WHERE vcr.user_id = '{user_id}' 
  AND vcr.status = 0
  AND vcr.end_date BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY)
ORDER BY vcr.end_date;
```

### 3.4 已过期但未更新状态的券
```sql
SELECT * FROM video_coupon_record
WHERE status = 0 
  AND end_date < NOW();
```

### 3.5 券使用关联追溯（券→订单→视频）
```sql
SELECT vcr.id AS coupon_id, vcr.coupon_id AS coupon_type,
       vo.id AS order_id, vo.video_id, vo.amount,
       vo.pay_status, vo.create_time
FROM video_coupon_record vcr
LEFT JOIN video_order vo ON vcr.order_id = vo.id
WHERE vcr.user_id = '{user_id}'
ORDER BY vcr.draw_time DESC;
```

---

## 四、套餐订单查询

### 4.1 用户套餐订单
```sql
SELECT vco.id, vco.combo_id, vco.video_count, vco.used_count,
       vco.pay_status, vco.end_time, vco.channel, vco.pay_channel,
       vco.refund_status, vco.create_time, vco.pay_time
FROM video_combo_order vco
WHERE vco.user_id = '{user_id}'
ORDER BY vco.create_time DESC;
```

### 4.2 套餐定义（当前可用的套餐）
```sql
SELECT id, price/100 AS price_yuan, video_count, 
       single_price/100 AS single_price_yuan,
       save_money/100 AS save_money_yuan,
       month AS valid_months, status
FROM video_combo
WHERE status = 1
ORDER BY display_order;
```

### 4.3 套餐使用率统计
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

### 4.4 未支付的套餐订单
```sql
SELECT * FROM video_combo_order
WHERE pay_status IS NULL OR pay_status = '支付失败';
```

### 4.5 已过期的套餐订单
```sql
SELECT * FROM video_combo_order
WHERE end_time IS NOT NULL 
  AND end_time < NOW()
  AND pay_status = '支付成功';
```

---

## 五、视频制作状态查询（核心）

### 5.1 完整状态机流转查询
```sql
-- video_client_status: 0=待解锁, 1=已解锁等待上传, 2=原片已上传,
--   3=下载中, 4=下载失败, 5=本地制作中, 6=制作失败, 7=制作完成, 8=已过期
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
       END AS status_text,
       vcs.client_id, vcs.created_at, vcs.updated_at,
       TIMESTAMPDIFF(MINUTE, vcs.created_at, vcs.updated_at) AS process_minutes
FROM video_client_status vcs
JOIN video_order vo ON vcs.video_id = vo.video_id
WHERE vo.user_id = '{user_id}'
ORDER BY vcs.updated_at DESC;
```

### 5.2 各状态视频数量统计
```sql
SELECT 
    CASE vcs.status
        WHEN 0 THEN '待解锁' WHEN 1 THEN '已解锁等待上传'
        WHEN 2 THEN '原片已上传' WHEN 3 THEN '下载中'
        WHEN 4 THEN '下载失败' WHEN 5 THEN '本地制作中'
        WHEN 6 THEN '制作失败' WHEN 7 THEN '制作完成'
        WHEN 8 THEN '已过期'
    END AS status_text,
    COUNT(*) AS video_count
FROM video_client_status vcs
GROUP BY vcs.status
ORDER BY vcs.status;
```

### 5.3 下载失败视频
```sql
SELECT vcs.video_id, vcs.client_id, vcs.updated_at,
       vo.video_id, vo.amount, vo.create_time
FROM video_client_status vcs
JOIN video_order vo ON vcs.video_id = vo.video_id
WHERE vcs.status = 4
ORDER BY vcs.updated_at DESC;
```

### 5.4 制作失败视频
```sql
SELECT vcs.video_id, vcs.client_id, vcs.updated_at,
       vo.amount, vo.create_time
FROM video_client_status vcs
JOIN video_order vo ON vcs.video_id = vo.video_id
WHERE vcs.status = 6
ORDER BY vcs.updated_at DESC;
```

### 5.5 正在制作中的视频（下载中+本地制作中）
```sql
SELECT vcs.video_id,
       CASE vcs.status WHEN 3 THEN '下载中' WHEN 5 THEN '本地制作中' END AS making_status,
       vcs.client_id, vcs.updated_at
FROM video_client_status vcs
WHERE vcs.status IN (3, 5)
ORDER BY vcs.updated_at DESC;
```

### 5.6 同一设备（client_id）的所有视频状态
```sql
SELECT vcs.video_id, vcs.status, vcs.client_id,
       vcs.created_at, vcs.updated_at
FROM video_client_status vcs
WHERE vcs.client_id = '{device_udid}'
ORDER BY vcs.updated_at DESC;
```

### 5.7 状态流转耗时分析
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

---

## 六、视频原片查询

### 6.1 用户视频的原片地址
```sql
SELECT vs.id, vs.order_id AS video_id, 
       vs.url_video, vs.url_bin, vs.create_time
FROM video_source vs
JOIN video_order vo ON vs.order_id = vo.video_id
WHERE vo.user_id = '{user_id}'
ORDER BY vs.create_time DESC;
```

### 6.2 未上传原片的已解锁视频
```sql
SELECT vo.id, vo.video_id, vo.user_id, vo.pay_status, vo.create_time
FROM video_order vo
LEFT JOIN video_source vs ON vo.video_id = vs.order_id
WHERE vo.user_id = '{user_id}'
  AND vo.pay_status = '支付成功'
  AND vs.id IS NULL;
```

---

## 七、视频目录查询

### 7.1 视频详情（根据video_id）
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

### 7.2 按分类查询视频
```sql
-- category: 单杆20+/单杆30+/单杆50+/单杆80+/单杆破百/局视频/进攻失败合集/长台精彩集锦
SELECT category, COUNT(*) AS cnt, 
       SUM(buy_times) AS total_buys,
       SUM(amount)/100 AS total_revenue_yuan
FROM video_list
GROUP BY category
ORDER BY total_revenue_yuan DESC;
```

### 7.3 用户解锁的视频列表（含视频元信息）
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

---

## 八、播放埋点查询

### 8.1 用户播放事件
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

### 8.2 视频播放统计
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

### 8.3 按来源类型统计播放量
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

### 8.4 热门视频排行（播放次数）
```sql
SELECT video_id, COUNT(*) AS play_count, SUM(play_ms)/1000 AS total_seconds
FROM video_event
GROUP BY video_id
ORDER BY play_count DESC
LIMIT 20;
```

---

## 九、退款查询

### 9.1 用户退款记录
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

### 9.2 退款失败记录排查
```sql
SELECT vr.id, vr.order_id, vr.user_id, vr.amount,
       vr.status, vr.wx_refund_result, vr.wx_notify_result,
       vr.create_time
FROM video_refund vr
WHERE vr.status = 3  -- 退款失败
ORDER BY vr.create_time DESC;
```

### 9.3 待审核退款
```sql
SELECT vr.id, vr.order_id, vr.user_id, vr.amount/100 AS amount_yuan,
       vo.video_id, vo.pay_status AS order_pay_status,
       vr.create_time
FROM video_refund vr
LEFT JOIN video_order vo ON vr.order_id = vo.id
WHERE vr.status = 0  -- 待审核
ORDER BY vr.create_time;
```

---

## 十、定价与促销查询

### 10.1 视频定价规则（固定价格）
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

### 10.2 当前生效的促销活动
```sql
-- discount: 10=1折, 85=85折
SELECT id, start_time, end_time, discount,
       CASE WHEN status = 1 THEN '正常' ELSE '停止' END AS activity_status,
       TIMESTAMPDIFF(HOUR, NOW(), end_time) AS hours_remaining
FROM video_promotion
WHERE status = 1 AND end_time > NOW()
ORDER BY discount;
```

### 10.3 历史折扣记录
```sql
SELECT category, base_price/100, discount_price/100, discount,
       latest_begin_time, latest_end_time, apply_times,
       create_user, update_time, update_user
FROM video_price
WHERE category = {category_id}
ORDER BY latest_begin_time DESC;
```

---

## 十一、支付订单查询

### 11.1 用户支付订单
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

### 11.2 支付订单与视频订单关联
```sql
SELECT po.pay_order_no, po.amount/100 AS amount_yuan, po.status AS pay_status,
       vo.id AS video_order_id, vo.video_id, vo.pay_status AS video_pay_status
FROM pay_order po
LEFT JOIN video_order vo ON po.pay_order_no = vo.wx_orderid
WHERE po.csm_user_id = '{user_id}'
ORDER BY po.time_start DESC;
```

---

## 十二、跨表关联查询

### 12.1 用户视频完整信息（订单+目录+状态+原片）
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
           WHEN 8 THEN '已过期'
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

### 12.2 视频全生命周期追踪
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
        WHEN 8 THEN '已过期'
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

### 12.3 套餐→券→使用 完整链路
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

---

## 十三、数据统计与报表

### 13.1 全量视频业务数据概览
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

### 13.2 各分类视频收入统计
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

### 13.3 每日视频解锁趋势
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

### 13.4 App vs 小程序 购买渠道分布
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

### 13.5 视频制作成功率
```sql
SELECT 
    CASE status
        WHEN 0 THEN '待解锁' WHEN 1 THEN '等待上传'
        WHEN 2 THEN '原片已上传' WHEN 3 THEN '下载中'
        WHEN 4 THEN '下载失败' WHEN 5 THEN '制作中'
        WHEN 6 THEN '制作失败' WHEN 7 THEN '制作完成'
        WHEN 8 THEN '已过期'
    END AS status_text,
    COUNT(*) AS count,
    ROUND(COUNT(*) / (SELECT COUNT(*) FROM video_client_status) * 100, 1) AS pct
FROM video_client_status
GROUP BY status
ORDER BY status;
```

### 13.6 视频播放Top排行
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

---

## 十四、问题排查SQL

### 14.1 已支付但无原片的视频
```sql
SELECT vo.id, vo.video_id, vo.user_id, vo.pay_status, vo.create_time
FROM video_order vo
LEFT JOIN video_source vs ON vo.video_id = vs.order_id
WHERE vo.pay_status = '支付成功'
  AND vs.id IS NULL;
```

### 14.2 状态不一致的视频（video_order与video_client_status不匹配）
```sql
SELECT vo.id, vo.video_id, vo.video_status AS order_status,
       vcs.status AS client_status
FROM video_order vo
LEFT JOIN video_client_status vcs ON vo.video_id = vcs.video_id
WHERE vo.video_status != 0  -- 已处理的订单
  AND (vcs.status IS NULL OR vcs.status = 0);  -- 但客户端状态异常
```

### 14.3 有券但从未使用的用户
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

### 14.4 套餐已支付但券未到账
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

### 14.5 视频过期但未更新状态
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

## 附录：核心表关系

```
ten_user (用户)
    │
    ├── video_order (视频订单) ←→ video_list (视频目录)
    │       │                        │
    │       ├── video_source (原片)   │
    │       ├── video_client_status (客户端状态)
    │       ├── video_event (播放事件)
    │       └── video_refund (退款)
    │
    ├── video_coupon_record (视频券)
    │
    └── video_combo_order (套餐订单) ←→ video_combo (套餐定义)
```

### 关键字段速查

| 表 | 用户关联字段 | 状态字段 | 金额单位 |
|---|---|---|---|
| video_order | user_id | pay_status / video_status | 分 |
| video_coupon_record | user_id | status (0/1/2) | — |
| video_combo_order | user_id | pay_status | 分 |
| video_client_status | (通过video_order关联) | status (0~8) | — |
| video_event | from_device | from_type | — |
| video_refund | user_id | status (0~4) | 分 |
| pay_order | csm_user_id | status (0~7) | 分 |
