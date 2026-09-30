# API 抓包规范（无需 root、无需 Reqable）

## 核心方法：adb logcat + Python requests

本 App 使用 Flutter + Dio HTTP 库，**默认开启调试日志**，可通过 `adb logcat` 直接抓取完整接口信息，无需任何抓包工具。

## 1. 实时查日志（类似 tail -f）

```bash
# 实时流式查看 App 网络请求（Ctrl+C 停止）
adb logcat | grep "flutter.*\[DIO\]"

# 只看请求 URL
adb logcat | grep "DIO.*uri:"

# 只看请求方法
adb logcat | grep "DIO.*method:"

# 只看请求参数
adb logcat | grep "DIO.*data:"

# 只看响应内容
adb logcat | grep "Response Text"

# 只看特定接口
adb logcat | grep "test.supervisions.cn"
```

## 2. 获取完整请求信息（用于 Python 复现）

```bash
# 清空日志 → 重启 App → 抓取 → 保存
adb logcat -c
adb shell am force-stop com.supervisions.snookermastercn
adb shell am start -n com.supervisions.snookermastercn/.MainActivity
sleep 15
adb logcat -d | grep "flutter.*\[" > app_log.txt
```

## 3. 从日志提取关键信息

从 `app_log.txt` 可提取：
- **API 域名**: `https://test.supervisions.cn`
- **接口 URL**: `DIO] uri:` 行
- **请求方法**: `DIO] method:` 行（全部为 POST）
- **请求参数**: `DIO] data:` 行（JSON 格式）
- **认证 Token**: `DIO]  Authorization:` 行（JWT）
- **refresh_token**: `DIO]  refresh_token:` 行

## 4. 用 Python 获取完整响应（v3.2 语义，2026-09-28 起）

logcat 对**大响应（>4000 字符）会截断**（Android logcat 单行限制）。工具 v3.2 的响应来源策略：

| 来源徽章 | 含义 | 响应体取自 | status/耗时取自 |
|---------|------|-----------|----------------|
| （无徽章）logcat | 捕获响应完整 | logcat 原文（真实） | Dio 响应段 status-code 头 / 行首时间戳差 |
| CAP+REPLAY | 捕获完整且重放成功 | logcat 原文 | 重放实测 |
| REPLAY | 捕获缺失/截断，重放成功 | 重放响应 | 重放实测 |
| TRUNC | 捕获截断且重放被拒 | 截断原文（仅供参考） | 推断 |
| DIFF 徽章 | 重放响应 ≠ 抓包响应 | **以抓包为准** | — |
| POLLUTED 徽章 | 请求体混入系统日志（历史数据） | — | — |
| 200? 徽章 | status 为 logcat 推断值，非实测 | — | — |

**重放闸门**（保证"重放请求 == 抓包请求"）：
- **绝对禁放**（非幂等/消耗性）：buyitUseComboV3（扣券）、appPostVideoRefund（退款）、deleteAccount、wechatLogin（消耗授权码）、loginBoxAfterScanningQrCode
- **测试环境放行 / 生产禁止**：埋点上报（event/track、addVideoEventFromMobile，测试对象）+ 幂等写（updateStatus、updateClientInfo、markVideoViewed*、saveDefaultClub，重发捕获体=重设同一状态）
- 请求体被污染/不配平/带尾巴 → 拒发；uri 疑似截断 → 拒发；App 侧 DioException → 拒发
- 生产环境未知接口 → 拒放；测试环境未知接口 → 允许（UI 标注）
- `--no-replay` 纯被动模式；`--replay-allow /path` 追加白名单
- 重放只发**捕获到的原始 headers**，不注入工具全局 token（公开接口重放 != 抓包的根因之一）

**混合分级重放决策（--replay-mode auto，默认）**：历史画像存于 `devtools/api_profile.json`
（每接口: 尺寸 p95/max、样本数、截断次数、重放次数、分级），30 天 TTL：

| 当次捕获 | 历史画像 | 动作 | 行来源 |
|---------|---------|------|--------|
| 完整 | small（max<3500B 且截断率≤20%） | 零重放 | logcat（status 取捕获头 statusCode，耗时取行首时间戳差） |
| 完整 | large / unstable | 主动重放 | CAP+REPLAY（+DIFF 校验） |
| 完整 | 未知 | 零重放，记尺寸学习 | logcat |
| 截断/丢失 | 任意 | 必重放 | REPLAY |

- `--replay-mode reactive` = 仅捕获不完整时重放；`always` = 允许即重放（旧行为）
- 画像安全优先级最低: DENY/TEST_ONLY 名单与 --no-replay 永远优先
- UI: 行徽章 `LG`(历史大响应) / `UNST`(高截断率)；Headers 页 History Profile 行展示 p95/样本/截断/重放

**回归测试**: `python devtools/test_state_machine.py`（17 条合成 logcat fixture，无需真机）

## 5. 注意事项

- **logcat 够用场景**: 小响应（用户信息、盒子状态、版本检查等 <1000 字符的接口）
- **必须用 Python 场景**: 大响应（对手列表、视频列表等 >4000 字符的接口），logcat 会截断
- **Token 有效期**: JWT Token 有过期时间，过期后需重新从 logcat 抓取
- **环境区分**: 当前连接测试服务器 `test.supervisions.cn`，生产环境域名不同
- **发现新接口**: 在 App 上操作到目标页面时，实时 logcat 会打印新接口 URL
- **隐藏接口匹配**: 精确路径或子路径边界（`/mp/user/info` 不再误隐 `/mp/user/infoV2`）

## 关键认知

> **logcat 负责发现接口与真实响应体，Python 重放负责补全完整响应与真实元数据；两者都在时以抓包为准并做一致性比对。**
> 遇到 App 显示的数据与脚本查询结果不一致时（如比赛场数），
> 说明 App 调用了另一个接口——用实时 logcat 找出它。
> 看到 DIFF 徽章 = 服务端状态在抓包与重放之间已变化（如券余额、列表排序），属预期，以抓包值写用例。
