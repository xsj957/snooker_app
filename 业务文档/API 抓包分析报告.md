# 斯诺克大师 App API 接口抓包分析报告

> **抓包方式**: ADB logcat（无需 Reqable、无需 root、无需 Frida）  
> **抓包时间**: 2026-08-06 00:08:54  
> **设备**: vivo X200 Pro (PD2405A)  
> **App 版本**: 1.0.0  
> **用户 ID**: 57d703dc-659a-4474-898e-b75efa1f2e0a  

---

## 一、基础信息

### API 域名
```
https://test.supervisions.cn
```

### 认证方式
**JWT Token + Refresh Token**

**请求头**:
```http
Content-Type: application/json
Accept: application/json
Authorization: eyJhbGciOiJIUzI1NiJ9...
refresh_token: ecbe9fe8a12e045be53db01e88f81da2
```

### JWT Token 解码

```json
{
  "sub": "cjsj",
  "iss": "cjsj",
  "exp": 1817467653,
  "authType": 4,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**Token 说明**:
| 字段 | 值 | 说明 |
|------|-----|------|
| sub | cjsj | 主题标识 |
| iss | cjsj | 签发者 |
| exp | 1817467653 | 过期时间戳（2027-08-04） |
| authType | 4 | 认证类型（4 = 微信登录） |
| userId | 57d703dc-... | 用户唯一标识 |

---

## 二、API 接口清单（App 启动时调用）

### 2.1 接口总览

| 序号 | 接口路径 | 方法 | 用途 | 调用时机 |
|------|----------|------|------|----------|
| 1 | `/mp/user/info` | POST | 获取用户信息 | 启动时 + 每 5 秒轮询 |
| 2 | `/mobile/getUserBoxStatus` | POST | 获取用户盒子状态 | 启动时 + 每 5 秒轮询 |
| 3 | `/mp/event/track` | POST | 埋点事件上报 | 启动时 + 页面切换 |
| 4 | `/mp/app/version/check` | POST | 检查 App 版本更新 | 启动时 |
| 5 | `/mp/coupon/checkEligibility` | POST | 检查视频券资格 | 启动时 |
| 6 | `/mp/coupon/trialList` | POST | 获取试用券列表 | 启动时 |
| 7 | `/mp/record/opponentListWithVideos` | POST | 获取对手列表和视频 | 启动时（首页） |
| 8 | `/mp/record/opponentStatistics` | POST | 获取对手统计数据 | 启动时（首页） |

---

## 三、接口详细分析

### 3.1 获取用户信息

**接口**: `POST /mp/user/info`

**请求体**:
```json
{
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**调用频率**: 启动时调用 1 次，之后每 5 秒轮询 1 次

**用途**: 获取用户基本信息（昵称、头像、俱乐部等）

---

### 3.2 获取用户盒子状态

**接口**: `POST /mobile/getUserBoxStatus`

**请求体**:
```json
{
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**调用频率**: 启动时调用 1 次，之后每 5 秒轮询 1 次

**用途**: 获取计分系统（工控机）连接状态，判断是否在线

---

### 3.3 埋点事件上报

**接口**: `POST /mp/event/track`

**请求体示例 1**（App 启动）:
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

**请求体示例 2**（页面浏览）:
```json
{
  "modelType": 1,
  "eventType": 5,
  "attrName": "matches",
  "attrValue": null,
  "clientType": 1,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**埋点字段说明**:
| 字段 | 说明 |
|------|------|
| modelType | 模块类型（1 = 首页） |
| eventType | 事件类型（1 = 启动, 5 = 页面浏览） |
| attrName | 属性名称 |
| attrValue | 属性值 |
| clientType | 客户端类型（1 = App） |
| userId | 用户 ID |

---

### 3.4 检查 App 版本

**接口**: `POST /mp/app/version/check`

**请求体**:
```json
{
  "platform": 2,
  "currentVersion": "1.0.0",
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**请求字段说明**:
| 字段 | 值 | 说明 |
|------|-----|------|
| platform | 2 | 平台（2 = Android） |
| currentVersion | 1.0.0 | 当前 App 版本 |
| userId | - | 用户 ID |

---

### 3.5 检查视频券资格

**接口**: `POST /mp/coupon/checkEligibility`

**请求体**:
```json
{
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**用途**: 检查用户是否有可用的视频券

---

### 3.6 获取试用券列表

**接口**: `POST /mp/coupon/trialList`

**请求体**:
```json
{
  "pageNo": 1,
  "pageSize": 100,
  "status": 0,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**请求字段说明**:
| 字段 | 值 | 说明 |
|------|-----|------|
| pageNo | 1 | 页码 |
| pageSize | 100 | 每页数量 |
| status | 0 | 状态（0 = 有效） |
| userId | - | 用户 ID |

---

### 3.7 获取对手列表和视频

**接口**: `POST /mp/record/opponentListWithVideos`

**请求体**:
```json
{
  "startTime": "2026-08-03 00:00:00",
  "endTime": "2026-08-09 23:59:59",
  "page": 1,
  "pageSize": 20,
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**请求字段说明**:
| 字段 | 值 | 说明 |
|------|-----|------|
| startTime | 2026-08-03 00:00:00 | 开始时间（本周一） |
| endTime | 2026-08-09 23:59:59 | 结束时间（本周日） |
| page | 1 | 页码 |
| pageSize | 20 | 每页数量 |
| userId | - | 用户 ID |

**用途**: 获取本周交手记录列表，包含视频信息

---

### 3.8 获取对手统计数据

**接口**: `POST /mp/record/opponentStatistics`

**请求体**:
```json
{
  "startTime": "2026-08-03 00:00:00",
  "endTime": "2026-08-09 23:59:59",
  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a"
}
```

**响应状态**: `200 OK`

**用途**: 获取本周交手统计数据（胜率、局数等）

---

## 四、轮询机制分析

### 4.1 轮询接口

App 启动后，以下 2 个接口会**每 5 秒轮询一次**：

1. `POST /mp/user/info` - 获取用户信息
2. `POST /mobile/getUserBoxStatus` - 获取盒子状态

### 4.2 轮询日志

```
00:08:54 首次调用
00:08:59 第 1 次轮询（+5s）
00:09:04 第 2 次轮询（+5s）
00:09:09 第 3 次轮询（+5s）
00:09:14 第 4 次轮询（+5s）
00:09:19 第 5 次轮询（+5s）
00:09:24 第 6 次轮询（+5s）
00:09:29 第 7 次轮询（+5s）
...持续轮询
```

### 4.3 轮询目的

**`getUserBoxStatus`**: 实时检测工控机（计分系统）是否在线
- 在线：显示"在线"状态，可以查看比赛数据
- 离线：显示"不在线"状态，部分功能受限

**`user/info`**: 实时刷新用户信息（可能包含消息通知等）

---

## 五、完整 API 调用时序图

```
App 启动
    │
    ├─► POST /mp/event/track          (埋点：App 冷启动)
    │
    ├─► POST /mp/event/track          (埋点：matches 页面)
    │
    ├─► POST /mobile/getUserBoxStatus (获取盒子状态) ─┐
    │                                                  │
    ├─► POST /mp/user/info            (获取用户信息) ──┤ 每 5 秒轮询
    │                                                  │
    ├─► POST /mp/coupon/checkEligibility (检查视频券)  │
    │                                                  │
    ├─► POST /mp/record/opponentListWithVideos (对手列表)│
    │                                                  │
    ├─► POST /mp/app/version/check    (检查版本更新)   │
    │                                                  │
    ├─► POST /mp/coupon/trialList     (试用券列表)     │
    │                                                  │
    └─► POST /mp/record/opponentStatistics (统计数据)  │
                                                       │
    ┌──────────────────────────────────────────────────┘
    │
    └─► 每 5 秒重复调用 getUserBoxStatus + user/info
```

---

## 六、抓包方法总结

### 6.1 使用 ADB logcat 抓包

**前提条件**:
- App 开启了调试日志（Flutter Dio 的 debugPrint）
- USB 调试已开启
- ADB 已连接设备

**操作命令**:
```bash
# 1. 清空日志
adb logcat -c

# 2. 重启 App
adb shell am force-stop com.supervisions.snookermastercn
adb shell am start -n com.supervisions.snookermastercn/.MainActivity

# 3. 抓取日志
adb logcat | grep -E "DIO|http|request|response" > app_log.txt

# 4. 分析日志
grep -E "DIO.*uri:|DIO.*method:|DIO.*data:" app_log.txt
```

### 6.2 优点

| 优点 | 说明 |
|------|------|
| ✅ 无需 root | 普通用户即可操作 |
| ✅ 无需安装证书 | 不依赖 HTTPS 解密 |
| ✅ 无需第三方工具 | 只用 ADB |
| ✅ 5 分钟搞定 | 快速出结果 |
| ✅ 完整请求信息 | URL、方法、请求体、请求头 |

### 6.3 限制

| 限制 | 说明 |
|------|------|
| ⚠️ 需要 App 开日志 | 不是所有 App 都开 |
| ⚠️ 响应内容不完整 | 日志中 Response Text 被截断 |
| ⚠️ 只能抓本机日志 | 无法抓其他设备 |

---

## 七、建议

### 7.1 对于开发团队

1. **生产环境关闭调试日志**：避免泄露敏感信息
2. **敏感数据脱敏**：Token、userId 等不应明文打印
3. **优化轮询机制**：5 秒轮询太频繁，建议改为 WebSocket 或更长间隔

### 7.2 对于测试团队

1. **用 logcat 快速验证接口**：无需配置复杂抓包环境
2. **关注轮询频率**：验证 5 秒轮询是否正常
3. **验证盒子状态切换**：在线/离线状态切换是否正常

### 7.3 对于安全团队

1. **Token 泄露风险**：日志中明文打印 JWT Token
2. **建议加密存储**：Token 不应明文存储在日志中
3. **建议混淆代码**：Release 版本应关闭所有调试日志

---

*报告生成时间: 2026-08-06*  
*抓包工具: ADB logcat*  
*分析工具: Claude Code*
