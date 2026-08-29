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

## 4. 用 Python 获取完整响应

logcat 对**大响应（>4000 字符）会截断**（Android logcat 单行限制），需用 Python requests 获取完整 data：

```python
# 脚本位置: devtools/api_tool.py
# 使用方式: python devtools/api_tool.py
# 包含: 实时抓包 + DevTools 风格 HTML 界面
```

## 5. 注意事项

- **logcat 够用场景**: 小响应（用户信息、盒子状态、版本检查等 <1000 字符的接口）
- **必须用 Python 场景**: 大响应（对手列表、视频列表等 >4000 字符的接口），logcat 会截断
- **Token 有效期**: JWT Token 有过期时间，过期后需重新从 logcat 抓取
- **环境区分**: 当前连接测试服务器 `test.supervisions.cn`，生产环境域名不同
- **发现新接口**: 在 App 上操作到目标页面时，实时 logcat 会打印新接口 URL

## 关键认知

> **logcat 负责发现接口，Python 负责获取完整响应。**
> 遇到 App 显示的数据与脚本查询结果不一致时（如比赛场数），
> 说明 App 调用了另一个接口——用实时 logcat 找出它。
