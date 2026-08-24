# 斯诺克大师 App API 接口完整响应分析

> **调试方式**: Python requests 直接调用（基于 adb logcat 抓包信息）  
> **调试时间**: 2026-08-06 00:20:07  
> **所有接口状态**: ✅ 全部返回 200 成功  

---

## 一、接口调用结果汇总

| 序号 | 接口 | 状态码 | 响应状态 |
|------|------|--------|----------|
| 1 | 埋点事件上报 | 200 | ✅ 成功 |
| 2 | 获取用户盒子状态 | 200 | ✅ 成功 |
| 3 | 获取用户信息 | 200 | ✅ 成功 |
| 4 | 检查 App 版本 | 200 | ✅ 成功 |
| 5 | 检查视频券资格 | 200 | ✅ 成功 |
| 6 | 获取试用券列表 | 200 | ✅ 成功 |
| 7 | 获取对手列表和视频 | 200 | ✅ 成功 |
| 8 | 获取对手统计数据 | 200 | ✅ 成功 |

---

## 二、各接口完整响应分析

### 2.1 埋点事件上报

**接口**: `POST /mp/event/track`

**请求参数**:
```json
{
  "modelType": 1,
  "eventType": 1,
  "attrName": "launch_source",
  "attrValue": "cold",
  "clientType": 1,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "success": true,
    "eventId": 7732
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
- `code: 0` 表示成功
- `eventId: 7732` 是该埋点事件的唯一 ID
- `success: true` 表示埋点上报成功

---

### 2.2 获取用户盒子状态

**接口**: `POST /mobile/getUserBoxStatus`

**请求参数**:
```json
{
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "deviceInfoId": 5045,
    "deviceSn": "0008600100000000107741",
    "clubName": "",
    "tableName": "",
    "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a",
    "isOnline": 0,
    "rating": 90,
    "adequacy": 0.088
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
| 字段 | 值 | 说明 |
|------|-----|------|
| deviceInfoId | 5045 | 设备信息 ID |
| deviceSn | 0008600100000000107741 | 设备序列号（工控机） |
| clubName | "" | 俱乐部名称（空 = 未绑定） |
| tableName | "" | 球桌名称（空 = 未绑定） |
| isOnline | 0 | **工控机离线状态**（0=离线，1=在线） |
| rating | 90 | 用户评级（90 分） |
| adequacy | 0.088 | 充足率（8.8%） |

**关键发现**: 
- 当前工控机处于**离线状态**（isOnline: 0）
- 这就是为什么 App 显示"不在线"的原因

---

### 2.3 获取用户信息

**接口**: `POST /mp/user/info`

**请求参数**:
```json
{
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a",
    "headImgUrl": "https://test.supervisions.cn/files/images/mpavatar/202607/e85a56ba-a378-4352-9a32-e27f4197d4b4.png",
    "nickname": "Natural",
    "rating": "--",
    "highestBreak": "32",
    "defaultMerchantAddressId": null,
    "defaultMerchantAddressName": null,
    "authType": 4,
    "email": ""
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
| 字段 | 值 | 说明 |
|------|-----|------|
| userId | 57d703dc-... | 用户唯一 ID |
| headImgUrl | https://... | 用户头像 URL |
| nickname | Natural | 用户昵称 |
| rating | -- | 评级（未定级） |
| highestBreak | 32 | 最高单杆得分（32 分） |
| authType | 4 | 认证类型（4 = 微信登录） |
| email | "" | 邮箱（未绑定） |

---

### 2.4 检查 App 版本

**接口**: `POST /mp/app/version/check`

**请求参数**:
```json
{
  "platform": 2,
  "currentVersion": "1.0.0",
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "needUpgrade": false,
    "forceUpgrade": false,
    "autoUpgrade": false,
    "latestVersion": null,
    "downloadUrl": null,
    "updateDesc": null,
    "packageSize": null,
    "md5": null,
    "appName": null
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
| 字段 | 值 | 说明 |
|------|-----|------|
| needUpgrade | false | **不需要更新** |
| forceUpgrade | false | 非强制更新 |
| autoUpgrade | false | 非自动更新 |
| latestVersion | null | 最新版本（null = 已是最新） |

**结论**: 当前版本 1.0.0 已是最新版本，无需更新

---

### 2.5 检查视频券资格

**接口**: `POST /mp/coupon/checkEligibility`

**请求参数**:
```json
{
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "msg": "drawn",
    "coupon": {
      "id": 381,
      "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a",
      "couponId": 1,
      "drawTime": "2026-07-29 16:15:13",
      "endDate": "2026-08-27 23:59:59",
      "status": 0,
      "orderId": 1950,
      "lastCompetitionId": null
    },
    "leftDay": 21,
    "lastCompetitionId": "fecd7c799ea5495ca23caceafaaca04b"
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
| 字段 | 值 | 说明 |
|------|-----|------|
| msg | drawn | 状态：已抽取 |
| coupon.id | 381 | 视频券记录 ID |
| coupon.couponId | 1 | 视频券类型 ID |
| coupon.drawTime | 2026-07-29 16:15:13 | 抽取时间 |
| coupon.endDate | 2026-08-27 23:59:59 | **有效期截止** |
| coupon.status | 0 | 状态（0 = 有效） |
| leftDay | 21 | **剩余 21 天** |

**关键发现**: 
- 用户有一张有效的视频券
- 有效期到 2026-08-27，还剩 21 天
- 视频券状态为"已抽取"（drawn）

---

### 2.6 获取试用券列表

**接口**: `POST /mp/coupon/trialList`

**请求参数**:
```json
{
  "pageNo": 1,
  "pageSize": 100,
  "status": 0,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "list": [],
    "total": 0
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
- `list: []` - 试用券列表为空
- `total: 0` - 总数为 0

**结论**: 用户当前没有试用券

---

### 2.7 获取对手列表和视频（核心接口）

**接口**: `POST /mp/record/opponentListWithVideos`

**请求参数**:
```json
{
  "startTime": "2026-08-03 00:00:00",
  "endTime": "2026-08-09 23:59:59",
  "page": 1,
  "pageSize": 20,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**（部分）:
```json
{
  "code": 0,
  "data": [
    {
      "date": "2026/08/05 17h53m",
      "dateWithTimeZone": "2026-08-05 17:53:40",
      "count": 1,
      "rate": 100,
      "videoStatus": 2,
      "videos": 2,
      "payed": 1,
      "detailedVideoStatus": 0,
      "expireTime": "2026-08-08 17:55:35",
      "videoList": [
        {
          "videoOrderId": 2005,
          "videoId": 12001,
          "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a",
          "payStatus": "支付成功",
          "payTime": "2026-08-05 20:21:24",
          "url": "",
          "isViewed": 1,
          "viewTime": "2026-08-05 20:27:25",
          "competitionId": "fecd7c799ea5495ca23caceafaaca04b",
          "videoCreateTime": "2026-08-05 17:55:05",
          "status": 1,
          "cover": null,
          "category": "局视频"
        },
        {
          "videoOrderId": null,
          "videoId": 12002,
          "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a",
          "payStatus": null,
          "payTime": null,
          "createTime": null,
          "url": null,
          "isViewed": null,
          "viewTime": null,
          "competitionId": "fecd7c799ea5495ca23caceafaaca04b",
          "videoCreateTime": "2026-08-05 17:55:35",
          "status": 0,
          "cover": null,
          "category": "局视频"
        }
      ],
      "aId": "57d703dc-659a-4474-898e-b75efa1f2e0a",
      "aName": "Natural",
      "aAvatar": "https://test.supervisions.cn/files/images/mpavatar/202607/e85a56ba-a378-4352-9a32-e27f4197d4b4.png",
      "aWins": 1,
      "bId": "对手 ID",
      "bName": "对手昵称",
      "bAvatar": "对手头像 URL",
      "bWins": 0,
      "aPingJi": 90,
      "bPingJi": 46
    }
  ]
}
```

**分析**:

**比赛信息**:
| 字段 | 值 | 说明 |
|------|-----|------|
| date | 2026/08/05 17h53m | 比赛时间 |
| rate | 100 | 胜率（100%） |
| videoStatus | 2 | 视频状态 |
| videos | 2 | 视频总数（2 个） |
| payed | 1 | 已支付数量（1 个） |
| expireTime | 2026-08-08 17:55:35 | 视频过期时间 |

**视频列表**:
| 视频 | 类型 | 状态 | 已观看 | URL |
|------|------|------|--------|-----|
| 12001 | 局视频 | status:1 | ✅ 已观看 | 空（待制作） |
| 12002 | 局视频 | status:0 |  未观看 | null（未支付） |

**双方信息**:
| 字段 | 值 | 说明 |
|------|-----|------|
| aName | Natural | 用户昵称 |
| aWins | 1 | 用户胜局（1 局） |
| bName | 对手昵称 | 对手昵称 |
| bWins | 0 | 对手胜局（0 局） |
| aPingJi | 90 | 用户评级（90 分） |
| bPingJi | 46 | 对手评级（46 分） |

---

### 2.8 获取对手统计数据

**接口**: `POST /mp/record/opponentStatistics`

**请求参数**:
```json
{
  "startTime": "2026-08-03 00:00:00",
  "endTime": "2026-08-09 23:59:59",
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**完整响应**:
```json
{
  "code": 0,
  "data": {
    "total": 5,
    "compC": 11,
    "compR": 36,
    "framC": 24,
    "framR": 42
  },
  "count": 0,
  "msg": "success"
}
```

**分析**:
| 字段 | 值 | 说明 |
|------|-----|------|
| total | 5 | 本周交手总场数（5 场） |
| compC | 11 | 比赛总局数（11 局） |
| compR | 36 | 比赛总回合数（36 回合） |
| framC | 24 | 框架得分（24 分） |
| framR | 42 | 框架总分（42 分） |

**统计**:
- 本周打了 **5 场比赛**
- 总共 **11 局**
- 胜率约 **57%**（24/42）

---

## 三、关键发现总结

### 3.1 用户状态

| 项目 | 状态 |
|------|------|
| 用户昵称 | Natural |
| 最高单杆 | 32 分 |
| 用户评级 | 90 分 |
| 登录方式 | 微信登录（authType: 4） |
| 工控机状态 | **离线**（isOnline: 0） |

### 3.2 视频券状态

| 项目 | 状态 |
|------|------|
| 有效视频券 | 1 张 |
| 有效期截止 | 2026-08-27（还剩 21 天） |
| 试用券 | 0 张 |

### 3.3 本周比赛数据

| 项目 | 数据 |
|------|------|
| 比赛场数 | 5 场 |
| 比赛局数 | 11 局 |
| 比赛回合 | 36 回合 |
| 框架得分 | 24/42（57%） |

### 3.4 视频状态

| 视频 ID | 类型 | 状态 | 已观看 | 过期时间 |
|---------|------|------|--------|----------|
| 12001 | 局视频 | 已支付 | ✅ | 2026-08-08 |
| 12002 | 局视频 | 未支付 |  | - |
| 11957 | 局视频 | 已支付 |  | 2026-11-02 |
| 11958 | 局视频 | 已支付 | ❌ | 2026-11-02 |

---

## 四、Python 脚本使用说明

### 4.1 运行方式

```bash
cd E:\work\cn_app_plus
python devtools/api_tool.py auto --full --html
```

### 4.2 输出内容

脚本会依次调用 8 个接口，并打印：
- 请求 URL
- 请求方法
- 请求参数
- 响应状态码
- 响应头
- 响应体（JSON 格式化）

### 4.3 自定义修改

如需修改参数，编辑 `devtools/api_tool.py` 中的预设接口配置：

```python
API_ENDPOINTS = {
    "接口名称": {
        "method": "POST",
        "url": "https://test.supervisions.cn/xxx",
        "data": {
            "userId": "你的 userId"
        }
    }
}
```

### 4.4 注意事项

⚠️ **Token 有效期**: JWT Token 有过期时间（exp: 1817467653 = 2027-08-04），过期后需要重新从 App 抓取

️ **测试环境**: 当前连接的是测试服务器（test.supervisions.cn），生产环境域名可能不同

---

*报告生成时间: 2026-08-06*  
*调试工具: Python requests + adb logcat*
