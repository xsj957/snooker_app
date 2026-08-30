# ADB 命令大全 — 斯诺克大师 App 专用

> 包名：`com.supervisions.snookermastercn`
> 设备型号：V2405A（vivo）
> 更新时间：2026-08-20

---

## 目录

1. [设备连接与管理](#1-设备连接与管理)
2. [App 安装与卸载](#2-app-安装与卸载)
3. [App 启停与清除](#3-app-启停与清除)
4. [日志抓取（logcat）](#4-日志抓取logcat)
5. [文件访问与导出](#5-文件访问与导出)
6. [网络抓包与接口调试](#6-网络抓包与接口调试)
7. [数据库操作](#7-数据库操作)
8. [权限管理](#8-权限管理)
9. [屏幕操作与截图](#9-屏幕操作与截图)
10. [性能监控](#10-性能监控)
11. [系统信息查询](#11-系统信息查询)
12. [模拟用户操作](#12-模拟用户操作)
13. [推送与通知调试](#13-推送与通知调试)
14. [Frida / Root 相关](#14-frida--root-相关)

---

## 1. 设备连接与管理

```bash
# 查看已连接设备
adb devices

# 查看设备详细信息（型号、序列号等）
adb devices -l

# 通过 WiFi 连接设备（先 USB 连接后执行）
adb tcpip 5555
adb connect <设备IP>:5555

# 断开 WiFi 连接
adb disconnect <设备IP>:5555

# 重启设备
adb reboot

# 重启到 recovery 模式
adb reboot recovery

# 重启到 bootloader 模式
adb reboot bootloader
```

---

## 2. App 安装与卸载

```bash
# 安装 APK（覆盖安装）
adb install -r snooker_master.apk

# 安装到指定设备（多设备时）
adb -s <device_id> install -r snooker_master.apk

# 卸载 App（保留数据）
adb shell pm uninstall -k com.supervisions.snookermastercn

# 彻底卸载 App
adb uninstall com.supervisions.snookermastercn

# 清除 App 数据（等同"清除缓存+数据"）
adb shell pm clear com.supervisions.snookermastercn

# 查看 App 安装信息
adb shell dumpsys package com.supervisions.snookermastercn | grep -E "versionCode|versionName|dataDir|flags|codePath"

# 查看 App 签名信息
adb shell dumpsys package com.supervisions.snookermastercn | grep -A 20 "signatures"
```

---

## 3. App 启停与清除

```bash
# 启动 App 主界面
adb shell am start -n com.supervisions.snookermastercn/.MainActivity

# 强制停止 App
adb shell am force-stop com.supervisions.snookermastercn

# 清除 App 缓存（不清除数据）
adb shell pm clear com.supervisions.snookermastercn

# 重启 App（先停止再启动）
adb shell am force-stop com.supervisions.snookermastercn && adb shell am start -n com.supervisions.snookermastercn/.MainActivity

# 获取 App 进程 PID
adb shell pidof com.supervisions.snookermastercn

# 查看 App 进程状态
adb shell ps | grep snooker
```

---

## 4. 日志抓取（logcat）

### 4.1 实时抓日志

```bash
# 实时查看所有日志
adb logcat

# 实时只看 App 的 Flutter/DIO 日志
adb logcat | grep "flutter.*\[DIO\]"

# 只看请求 URL
adb logcat | grep "DIO.*uri:"

# 只看请求方法
adb logcat | grep "DIO.*method:"

# 只看请求参数
adb logcat | grep "DIO.*data:"

# 只看响应内容
adb logcat | grep "Response Text"

# 只看特定接口的日志
adb logcat | grep "test.supervisions.cn"

# 只看视频相关的日志
adb logcat | grep -iE "video|视频|download|制作|unlock"

# 只看文件路径相关的日志
adb logcat | grep -iE "/data/|/sdcard/|/storage/|path|file|cache" | grep flutter

# 按 tag 过滤
adb logcat -s flutter

# 按级别过滤（只显示 Error 和 Warn）
adb logcat *:E *:W

# 按 PID 过滤（只抓本 App 的日志）
PID=$(adb shell pidof com.supervisions.snookermastercn)
adb logcat --pid=$PID
```

### 4.2 抓取历史日志

```bash
# 获取最近 500 行日志
adb logcat -d -t 500

# 获取最近日志并保存到文件
adb logcat -d > app_log.txt

# 只抓 App 的日志到文件
adb logcat -d | grep "flutter" > flutter_log.txt

# 清空日志缓冲区（在测试操作前执行）
adb logcat -c

# 清空后重启 App 再抓日志（标准测试流程）
adb logcat -c
adb shell am force-stop com.supervisions.snookermastercn
adb shell am start -n com.supervisions.snookermastercn/.MainActivity
sleep 15
adb logcat -d | grep "flutter.*\[" > app_log.txt
```

### 4.3 日志输出格式

```bash
# 带时间的长格式
adb logcat -v time

# 线程时间格式
adb logcat -v threadtime

# 导出为可读格式到文件
adb logcat -v threadtime -d > app_log_full.txt
```

---

## 5. 文件访问与导出

> ⚠️ **重要 1**：`/data/data/<包名>/` 是 App 私有目录，普通 `adb shell cd` 无法访问，必须用 `run-as`。
>
> ⚠️ **重要 2**：导出**二进制文件**（视频/图片/数据库）时，**禁止**用 `adb shell "run-as ... cat ..."` + PowerShell `>` 重定向！PowerShell 会把二进制流当文本处理，自动插入 UTF-16 BOM 并在每个字节间填充 `00`，导致文件损坏。正确方式见 5.2。

### 5.1 查看文件

```bash
# 列出 App 私有目录所有文件
adb shell "run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/ -type f"

# 列出 App 私有目录所有目录
adb shell "run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/ -type d"

# 递归列出 app_flutter 目录
adb shell "run-as com.supervisions.snookermastercn ls -laR /data/data/com.supervisions.snookermastercn/app_flutter/"

# 递归列出 cache 目录
adb shell "run-as com.supervisions.snookermastercn ls -laR /data/data/com.supervisions.snookermastercn/cache/"

# 搜索视频文件
adb shell "run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/ -name '*.mp4'"

# 搜索大于 1MB 的文件
adb shell "run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/ -type f -size +1M"

# 搜索最近修改的文件
adb shell "run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/ -type f -mmin -60"

# 查看文件内容（文本文件）
adb shell "run-as com.supervisions.snookermastercn cat /data/data/com.supervisions.snookermastercn/shared_prefs/FlutterSharedPreferences.xml"
```

### 5.2 导出文件到电脑

> ⚠️ **PowerShell 用户必读**：PowerShell 的 `>` 重定向会把所有输出强制走文本编码（UTF-32LE），**任何二进制文件都会被损坏**（每个字节间插入 `00`，文件膨胀约 1.36×）。`adb exec-out` 也救不了，因为问题在 PowerShell 不在 adb。

#### ✅ 唯一可靠方式：Python subprocess（绕过 PowerShell 编码）

```bash
# 导出单个视频文件（在 PowerShell 中执行）
python3 -c "
import subprocess
proc = subprocess.run(['adb','exec-out','run-as com.supervisions.snookermastercn cat /data/data/com.supervisions.snookermastercn/app_flutter/12326_20260820215249.mp4'], capture_output=True)
open('E:/work/cn_app_plus/video.mp4','wb').write(proc.stdout)
print(f'Done: {len(proc.stdout)} bytes')
"

# 导出单个文本文件（XML/txt/log 等文本文件不受影响，可以正常用 > 重定向）
adb shell "run-as com.supervisions.snookermastercn cat /data/data/com.supervisions.snookermastercn/shared_prefs/FlutterSharedPreferences.xml" > prefs.xml
```

#### ✅ Git Bash / CMD 用户：管道方式

```bash
# Git Bash 中 cat 是二进制安全的，管道方式可用（但会多出少量 shell 噪声）
adb shell "run-as com.supervisions.snookermastercn cat /data/data/com.supervisions.snookermastercn/app_flutter/12326_20260820215249.mp4" | cat > video.mp4
```

#### ❌ 不可用的方式

```bash
# ❌ PowerShell > 重定向：二进制文件会被编码损坏
adb exec-out "run-as com.supervisions.snookermastercn cat xxx.mp4" > video.mp4

# ❌ cp + adb pull：Android 10+ 分区存储，run-as 无法写入 sdcard 任何路径
adb shell "run-as com.supervisions.snookermastercn cp xxx.mp4 /sdcard/Download/video.mp4"
# → cp: /sdcard/Download/video.mp4: Permission denied

# ❌ adb pull 直接拉取：无 root 权限无法访问 /data/data/ 目录
adb pull /data/data/com.supervisions.snookermastercn/app_flutter/xxx.mp4 .
# → adb: error: failed to stat remote object
```

#### 批量导出所有视频

```bash
python3 -c "
import subprocess, os

# 获取文件列表
result = subprocess.run(['adb','shell','run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/app_flutter/ -name *.mp4'], capture_output=True, text=True)
files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]

os.makedirs('videos', exist_ok=True)
for f in files:
    fname = os.path.basename(f)
    proc = subprocess.run(['adb','exec-out',f'run-as com.supervisions.snookermastercn cat {f}'], capture_output=True)
    path = os.path.join('videos', fname)
    with open(path, 'wb') as out:
        out.write(proc.stdout)
    print(f'{fname}: {len(proc.stdout)} bytes')
"
```

### 导出方式速查

| 文件类型 | PowerShell 下的正确方式 | 说明 |
|---------|----------------------|------|
| 视频 `.mp4`、图片 `.png`、数据库 `.db` | **Python subprocess**（见上方代码） | `>` 和 `adb exec-out >` 都会被 PowerShell 编码损坏；`cp + pull` 因分区存储权限被拒 |
| XML、txt、log、json | `adb shell "run-as ... cat ..."` > | 文本文件，`>` 重定向安全 |

---

### 5.3 推送文件到手机

```bash
# 推送文件到 App 私有目录（通过 run-as 间接操作）
adb push local_file.txt /sdcard/Download/local_file.txt
adb shell "run-as com.supervisions.snookermastercn cp /sdcard/Download/local_file.txt /data/data/com.supervisions.snookermastercn/files/local_file.txt"

# 推送文件到 sdcard
adb push local_file.mp4 /sdcard/Download/local_file.mp4
```

### 5.4 sdcard 公共目录操作

```bash
# 列出 sdcard 根目录
adb shell ls -la /sdcard/

# 搜索 sdcard 上的视频文件
adb shell "find /sdcard/ -name '*.mp4'" 2>/dev/null | head -30

# 搜索最近 2 天修改的大文件
adb shell "find /sdcard/ -type f -size +5M -mtime -2" 2>/dev/null

# 查看 App 外部存储目录
adb shell ls -la /sdcard/Android/data/com.supervisions.snookermastercn/ 2>/dev/null

# 查看 Downloads 目录
adb shell ls -la /sdcard/Download/

# 查看 DCIM（相机照片/视频）
adb shell ls -la /sdcard/DCIM/Camera/
```

---

## 6. 网络抓包与接口调试

### 6.1 通过 logcat 抓接口（无 root、无 Reqable）

```bash
# 标准流程：清日志 → 重启 App → 操作 → 抓日志
adb logcat -c
adb shell am force-stop com.supervisions.snookermastercn
adb shell am start -n com.supervisions.snookermastercn/.MainActivity
sleep 5
adb logcat -d | grep "flutter.*\[DIO\]" > dio_log.txt

# 提取所有 API URL
adb logcat -d | grep "DIO.*uri:" | grep "supervisions"

# 提取所有请求参数
adb logcat -d | grep "DIO.*data:" | grep -v "headers\|followRedirects\|responseType"

# 提取所有响应内容
adb logcat -d | grep "Response Text" -A 1
```

### 6.2 通过 API 直接查询（Python requests）

```bash
# 从日志中提取 Token 和 User ID
adb logcat -d | grep "Authorization:" | head -1
adb logcat -d | grep "user_id\|userId" | grep "flutter" | head -1
```

```python
# devtools/api_tool.py — DevTools 抓包调试工具（自动获取完整响应）
# 使用方式：python devtools/api_tool.py auto --full --html
TOKEN = "从 DIO Authorization 行提取的 JWT Token"
USER_ID = "从 FlutterSharedPreferences 或日志中提取的 userId"
BASE_URL = "https://test.supervisions.cn"

# 示例：查询我的视频列表
import requests
headers = {
    "Content-Type": "application/json",
    "Authorization": TOKEN,
    "refresh_token": "从日志提取的 refresh_token"
}

# 已解锁视频列表
resp = requests.post(f"{BASE_URL}/video/videoClient/myVideos/readyV2",
                     json={"userId": USER_ID, "lang": "zh_CN"}, headers=headers)
print(resp.json())

# 制作中视频列表
resp = requests.post(f"{BASE_URL}/video/videoClient/myVideos/processingV2",
                     json={"userId": USER_ID, "lang": "zh_CN"}, headers=headers)
print(resp.json())

# 用户信息
resp = requests.post(f"{BASE_URL}/mp/user/info",
                     json={"userId": USER_ID, "lang": "zh_CN"}, headers=headers)
print(resp.json())

# 比赛列表（含视频）
resp = requests.post(f"{BASE_URL}/mp/record/competitionListWithVideos",
                     json={"userId": USER_ID, "lang": "zh_CN"}, headers=headers)
print(resp.json())

# 交手记录（含视频）
resp = requests.post(f"{BASE_URL}/mp/record/opponentListWithVideos",
                     json={"userId": USER_ID, "lang": "zh_CN"}, headers=headers)
print(resp.json())

# 视频统计
resp = requests.post(f"{BASE_URL}/video/videoClient/getVideoStatistics",
                     json={"userId": USER_ID, "lang": "zh_CN"}, headers=headers)
print(resp.json())

# 更新视频状态
resp = requests.post(f"{BASE_URL}/video/videoClient/updateStatus",
                     json={"clientId": "设备ID", "status": 3, "videoId": 12326,
                           "videoOrderId": 2107, "userId": USER_ID, "lang": "zh_CN"},
                     headers=headers)
print(resp.json())

# 设备盒子状态
resp = requests.post(f"{BASE_URL}/mobile/getUserBoxStatus",
                     json={"userId": USER_ID}, headers=headers)
print(resp.json())
```

### 6.3 常用接口速查

| 接口 | 方法 | 用途 |
|------|------|------|
| `/mp/user/info` | POST | 用户信息 |
| `/mp/record/competitionListWithVideos` | POST | 比赛列表（含视频） |
| `/mp/record/opponentListWithVideos` | POST | 交手记录（含视频） |
| `/video/videoClient/myVideos/readyV2` | POST | 已解锁视频列表 |
| `/video/videoClient/myVideos/processingV2` | POST | 制作中视频列表 |
| `/video/videoClient/getVideoStatistics` | POST | 视频统计 |
| `/video/videoClient/updateStatus` | POST | 更新视频状态 |
| `/mobile/getUserBoxStatus` | POST | 设备盒子状态 |

---

## 7. 数据库操作

> 数据库连接信息：`121.40.243.17:3306`（supervisions 库）
> 账号：`linjiakun` / 密码：`Ljk@123456`

```bash
# 通过 adb 访问 App 本地数据库（SQLite）
adb shell "run-as com.supervisions.snookermastercn ls -la /data/data/com.supervisions.snookermastercn/databases/"

# 导出 App 本地数据库到电脑
adb shell "run-as com.supervisions.snookermastercn cp /data/data/com.supervisions.snookermastercn/databases/xxx.db /sdcard/Download/xxx.db"
adb pull /sdcard/Download/xxx.db .

# 用 sqlite3 查看导出的数据库（需要在电脑上安装 sqlite3）
sqlite3 xxx.db ".tables"
sqlite3 xxx.db ".schema"
sqlite3 xxx.db "SELECT * FROM table_name LIMIT 10;"
```

### 远程数据库常用查询

```bash
# 通过 mysql 命令行连接（需要先安装 mysql client）
mysql -h 121.40.243.17 -P 3306 -u linjiakun -p'Ljk@123456' supervisions

# 根据手机号查用户
SELECT id, phone, nickname, union_id FROM ten_user WHERE phone = '手机号';

# 查用户的视频订单
SELECT * FROM video_order WHERE user_id = '用户UUID' ORDER BY create_time DESC LIMIT 20;

# 查用户的视频列表
SELECT * FROM video_list WHERE merchant_address_id = 俱乐部ID ORDER BY create_time DESC;

# 查视频原片地址
SELECT * FROM video_source WHERE video_id = 视频ID;

# 查视频状态
SELECT * FROM video_client_status WHERE user_id = '用户UUID' AND video_id = 视频ID;

# 查视频券记录
SELECT * FROM video_coupon_record WHERE user_id = '用户UUID' ORDER BY create_time DESC;

# 查播放事件
SELECT * FROM video_event WHERE user_id = '用户UUID' AND from_type = 3 ORDER BY create_time DESC;

# 查用户比赛记录（通过 inning 表）
SELECT * FROM ten_inning WHERE left_id = '用户UUID' OR right_id = '用户UUID' ORDER BY create_time DESC LIMIT 20;
```

---

## 8. 权限管理

```bash
# 查看 App 所有权限状态
adb shell dumpsys package com.supervisions.snookermastercn | grep "permission"

# 授予权限
adb shell pm grant com.supervisions.snookermastercn android.permission.CAMERA
adb shell pm grant com.supervisions.snookermastercn android.permission.READ_MEDIA_VIDEO
adb shell pm grant com.supervisions.snookermastercn android.permission.READ_MEDIA_IMAGES
adb shell pm grant com.supervisions.snookermastercn android.permission.READ_MEDIA_VISUAL_USER_SELECTED
adb shell pm grant com.supervisions.snookermastercn android.permission.POST_NOTIFICATIONS

# 撤销权限
adb shell pm revoke com.supervisions.snookermastercn android.permission.CAMERA

# 查看所有已授予的权限
adb shell dumpsys package com.supervisions.snookermastercn | grep "granted=true"
```

---

## 9. 屏幕操作与截图

```bash
# 截图并保存到电脑
adb shell screencap -p /sdcard/Download/screenshot.png
adb pull /sdcard/Download/screenshot.png ./screenshot.png

# 一键截图到电脑当前目录
adb exec-out screencap -p > screenshot.png

# 录屏（最长 180 秒，Ctrl+C 停止）
adb shell screenrecord /sdcard/Download/record.mp4
adb pull /sdcard/Download/record.mp4 ./record.mp4

# 录屏指定时长（30秒）
adb shell screenrecord --time-limit 30 /sdcard/Download/record.mp4
adb pull /sdcard/Download/record.mp4 ./record.mp4

# 获取屏幕分辨率
adb shell wm size

# 获取屏幕密度
adb shell wm density

# 修改屏幕密度（测试 UI 适配）
adb shell wm density 320
adb shell wm density reset  # 恢复默认
```

---

## 10. 性能监控

```bash
# 查看 App CPU 和内存占用（实时）
adb shell top | grep snooker

# 查看 App 内存详情
adb shell dumpsys meminfo com.supervisions.snookermastercn

# 查看 App 内存占用摘要
adb shell dumpsys meminfo com.supervisions.snookermastercn | grep -E "TOTAL|Java Heap|Native Heap"

# 查看 App 进程信息
PID=$(adb shell pidof com.supervisions.snookermastercn)
adb shell cat /proc/$PID/status | grep -E "VmRSS|VmSize|Threads"

# 查看 GPU 渲染信息
adb shell dumpsys gfxinfo com.supervisions.snookermastercn

# 查看电池使用情况
adb shell dumpsys batterystats com.supervisions.snookermastercn

# 查看 App 磁盘 I/O
adb shell cat /proc/$(adb shell pidof com.supervisions.snookermastercn)/io

# 查看 App 打开的文件描述符
PID=$(adb shell pidof com.supervisions.snookermastercn)
adb shell ls -la /proc/$PID/fd/ | grep -v "socket\|pipe\|eventpoll\|anon_inode"

# 查看 App 内存映射
PID=$(adb shell pidof com.supervisions.snookermastercn)
adb shell cat /proc/$PID/maps | grep -E "\.so|\.dex|flutter"
```

---

## 11. 系统信息查询

```bash
# 查看设备基本信息
adb shell getprop ro.product.model      # 型号
adb shell getprop ro.product.brand      # 品牌
adb shell getprop ro.build.version.release  # Android 版本
adb shell getprop ro.build.version.sdk  # API Level
adb shell getprop ro.product.cpu.abi    # CPU 架构

# 查看设备存储空间
adb shell df -h /sdcard
adb shell df -h /data

# 查看内存信息
adb shell cat /proc/meminfo | head -5

# 查看已安装的所有包
adb shell pm list packages | grep snooker

# 查看 App 安装路径
adb shell pm path com.supervisions.snookermastercn

# 查看 App 所有组件（Activity/Service/Receiver/Provider）
adb shell dumpsys package com.supervisions.snookermastercn | grep -E "Activity|Service|Receiver|Provider" | grep -v " " | sort -u

# 查看设备唯一标识
adb shell settings get secure android_id
```

---

## 12. 模拟用户操作

```bash
# 模拟点击（x, y 坐标）
adb shell input tap 540 1200

# 模拟滑动（从 x1,y1 到 x2,y2，持续 ms 毫秒）
adb shell input swipe 540 1500 540 500 300

# 模拟返回键
adb shell input keyevent KEYCODE_BACK
# 或
adb shell input keyevent 4

# 模拟 Home 键
adb shell input keyevent KEYCODE_HOME
# 或
adb shell input keyevent 3

# 模拟菜单键
adb shell input keyevent KEYCODE_MENU

# 模拟音量+
adb shell input keyevent KEYCODE_VOLUME_UP

# 模拟音量-
adb shell input keyevent KEYCODE_VOLUME_DOWN

# 模拟电源键（锁屏/唤醒）
adb shell input keyevent KEYCODE_POWER

# 输入文本
adb shell input text "hello"

# 模拟长按
adb shell input swipe 540 1200 540 1200 2000
```

---

## 13. 推送与通知调试

```bash
# 查看 App 的通知渠道
adb shell dumpsys notification --package=com.supervisions.snookermastercn

# 发送测试通知（需要 App 有对应的 NotificationChannel）
adb shell "cmd notification post test_channel 1 --package com.supervisions.snookermastercn --tag test --title '测试通知' --text '这是一条测试推送'"

# 查看通知历史
adb shell dumpsys notification --noredact

# 清除所有通知
adb shell cmd notification cancel_all

# 查看极光推送相关日志
adb logcat -d | grep -iE "jpush|jiguang|极光"

# 查看通知权限状态
adb shell dumpsys package com.supervisions.snookermastercn | grep "POST_NOTIFICATIONS"
```

---

## 14. Frida / Root 相关

```bash
# 启动 Frida Server（已部署在 /data/local/tmp/）
adb shell "/data/local/tmp/frida-server &"

# 查看 Frida 是否运行
adb shell "ps | grep frida"

# 列出当前运行的进程
frida-ps -U

# Hook App 进程
frida -U -f com.supervisions.snookermastercn

# 查看 Frida Server 版本
/data/local/tmp/frida-server --version

# 如果 frida-server 崩溃，重新启动
adb shell "kill $(adb shell ps | grep frida-server | awk '{print $2}')"
adb shell "/data/local/tmp/frida-server &"

# PerfDog 性能测试工具（已部署）
adb shell "/data/local/tmp/PerfDogServer &"
```

---

## 附录 A：App 文件目录结构

```
/data/data/com.supervisions.snookermastercn/
── app_flutter/              ← Flutter 资源 + 下载/制作的视频
│   ├── flutter_assets/       ← Flutter 编译产物
│   │   ├── kernel_blob.bin   ← Dart 编译产物（~92MB）
│   │   ├── isolate_snapshot_data
│   │   └── vm_snapshot_data
│   ├── res_timestamp-*       ← 资源时间戳
│   └── {videoId}_{timestamp}.mp4  ← 制作完成的视频文件 ⭐
├── cache/                    ← 素材模板 + 制作中间文件
│   ├── start.mp4             ← 片头模板（84KB）
│   ├── end.mp4               ← 片尾模板（85KB）
│   ├── head.aac              ← 片头音频
│   ├── tail.aac              ← 片尾音频
│   ├── turnover.aac          ← 背景音乐
│   ├── logo.png              ← Logo
│   ├── score_bar_bg.png      ← 比分条背景
│   ├── match_replay.png      ← 比赛回放封面
│   ├── fail_replay.png       ← 失败回放封面
│   ├── thickness_bg.png      ← 厚薄度背景
│   ├── ball_speed.png        ← 杆速背景
│   ├── angle1.png            ← 角度图
│   ├── bg.png                ← 背景图
│   ├── union.png             ← Union 图
│   └── instrument/           ← 埋点缓存（通常为空）
├── code_cache/               ← JIT 编译缓存
│   ├── flutter_engine/       ← Skia 引擎缓存
│   └── snooker-appUEUBTE/    ← Dart JIT 缓存
├── databases/                ← SQLite 数据库
│   └── com.google.android.datatransport.events
├── files/                    ← 通用文件
│   ├── profileInstalled
│   └── profileinstaller_*.dat
└── shared_prefs/             ← SharedPreferences
    ├── FlutterSharedPreferences.xml  ← Token、用户ID等 
    ├── com.supervisions.snookermastercn_preferences.xml
    ├── com.facebook.sdk.*    ← Facebook SDK
    └── com.google.mlkit.*    ← ML Kit
```

---

## 附录 B：常用一键命令组合

```bash
#  重启 App 并抓日志
adb shell am force-stop com.supervisions.snookermastercn && adb logcat -c && adb shell am start -n com.supervisions.snookermastercn/.MainActivity && sleep 3 && adb logcat -d | grep flutter

# 📋 导出所有视频文件到电脑 ./videos/ 目录（PowerShell 中执行）
python3 -c "
import subprocess, os
result = subprocess.run(['adb','shell','run-as com.supervisions.snookermastercn find /data/data/com.supervisions.snookermastercn/app_flutter/ -name *.mp4'], capture_output=True, text=True)
files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
os.makedirs('videos', exist_ok=True)
for f in files:
    fname = os.path.basename(f)
    proc = subprocess.run(['adb','exec-out',f'run-as com.supervisions.snookermastercn cat {f}'], capture_output=True)
    path = os.path.join('videos', fname)
    with open(path, 'wb') as out: out.write(proc.stdout)
    print(f'{fname}: {len(proc.stdout)} bytes')
"

# 📱 一键截图
adb exec-out screencap -p > screenshot_$(date +%Y%m%d_%H%M%S).png

# 🎬 录屏 30 秒
adb shell screenrecord --time-limit 30 /sdcard/Download/record_$(date +%Y%m%d_%H%M%S).mp4 && adb pull /sdcard/Download/record_*.mp4 .

# 🔍 快速查看视频列表 API 响应
adb logcat -d -t 50 | grep "myVideos" -A 3

#  清除 App 数据并重启
adb shell pm clear com.supervisions.snookermastercn && adb shell am start -n com.supervisions.snookermastercn/.MainActivity

#  查看 App 内存占用
adb shell dumpsys meminfo com.supervisions.snookermastercn | grep -E "TOTAL Pss|Java Heap|Native Heap"

# 🔑 提取 Token
adb shell "run-as com.supervisions.snookermastercn cat /data/data/com.supervisions.snookermastercn/shared_prefs/FlutterSharedPreferences.xml" | grep "access_token"
```

---

## 附录 C：视频业务状态机

| 值 | 状态 | 说明 |
|----|------|------|
| 0 | 待解锁 | 用户未解锁 |
| 1 | 已解锁等待上传 | 解锁成功，等待工控机上传原片 |
| 2 | 原片已上传 | 原片已上传到腾讯云 |
| 3 | 下载中 | App 正在下载原片 |
| 4 | 下载失败 | 下载失败 |
| 5 | 本地制作中 | App 本地制作视频 |
| 6 | 制作失败 | 制作失败 |
| 7 | 制作完成 | 视频制作成功 |
| 8 | 已过期 | 视频已过期 |

> 小程序只展示 5 种文案：制作中（1/3/5）、制作失败（4/6）、制作成功（7）、已过期（8）

---

## 附录 D：排查问题标准流程

### 视频制作问题排查

```bash
# 1. 查看当前视频状态
adb logcat -d | grep "videoId\|videoStatus\|status" | grep flutter | tail -20

# 2. 查看下载进度
adb logcat -d | grep -iE "下载|download|progress" | grep flutter | tail -10

# 3. 查看制作进度
adb logcat -d | grep -iE "制作|make|render|concat" | grep flutter | tail -10

# 4. 检查视频文件是否存在
adb shell "run-as com.supervisions.snookermastercn ls -la /data/data/com.supervisions.snookermastercn/app_flutter/"

# 5. 检查缓存空间
adb shell df -h /data

# 6. 查看 App 内存
adb shell dumpsys meminfo com.supervisions.snookermastercn | grep TOTAL
```

### 接口问题排查

```bash
# 1. 清空日志
adb logcat -c

# 2. 重启 App
adb shell am force-stop com.supervisions.snookermastercn
adb shell am start -n com.supervisions.snookermastercn/.MainActivity

# 3. 操作 App 到目标页面
# （手动操作...）

# 4. 使用 DevTools 工具自动抓包（推荐）
python devtools/api_tool.py auto --full --html

# 或手动抓取日志
adb logcat -d | grep "DIO" > app_log.txt

# 5. 提取关键信息
grep "uri:" app_log.txt        # 所有接口 URL
grep "data:" app_log.txt      # 所有请求参数
grep "Response Text" -A 1 app_log.txt  # 所有响应
```

### 登录/Token 问题排查

```bash
# 查看当前 Token
adb shell "run-as com.supervisions.snookermastercn cat /data/data/com.supervisions.snookermastercn/shared_prefs/FlutterSharedPreferences.xml"

# 查看 Token 有效期
# 在 FlutterSharedPreferences.xml 中查找 expires_time 字段

# 刷新 Token（通过重新登录或重启 App）
adb shell am force-stop com.supervisions.snookermastercn
adb shell am start -n com.supervisions.snookermastercn/.MainActivity
```

---

> **维护说明**：本文档随项目开发持续更新，新增命令请添加到对应章节末尾。
