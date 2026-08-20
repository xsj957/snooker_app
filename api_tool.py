#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 抓包调试工具
功能：实时查日志 + 自动提取接口 + 获取完整响应
用法：python api_tool.py <command> [options]

命令：
  log     - 实时查看 App 网络日志（类似 tail -f | grep）
  extract - 从日志文件提取所有 API 接口信息
  call    - 调用指定接口并显示完整响应
  auto    - 实时监控 + 自动发现新接口 + 自动获取完整响应
  list    - 列出所有已发现的接口

全局参数：
  -s, --device  指定 ADB 设备 ID（多设备时必须指定）
                设备 ID 可通过 adb devices 查看
                示例：python api_tool.py auto -s 设备ID

auto 专用参数：
  --full        自动用 Python requests 调用每个请求获取完整响应
                （绕过 logcat 单行截断限制，大响应也能完整显示）
                示例：python api_tool.py auto --full
"""

import argparse
import subprocess
import re
import json
import sys
import os
import time
import threading
import queue
import requests
from datetime import datetime
from collections import OrderedDict

# ============== 配置 ==============

# 禁用代理（避免公司网络代理导致连接失败）
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

BASE_URL = "https://test.supervisions.cn"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjanNqIiwiaXNzIjoiY2pzaiIsImV4cCI6MTgxNzQ2NzY1MywiYXV0aFR5cGUiOjQsInVzZXJJZCI6IjU3ZDcwM2RjLTY1OWEtNDQ3NC04OThlLWI3NWVmYTFmMmUwYSJ9.evzNsb2k7yv33yNU8BDsit7FCN-eNCQk5iD5YL12h2c",
    "refresh_token": "ecbe9fe8a12e045be53db01e88f81da2"
}

USER_ID = "57d703dc-659a-4474-898e-b75efa1f2e0a"


def get_adb_device():
    """动态获取已连接的 ADB 设备序列号，无设备则返回 None"""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().splitlines()
        for line in lines[1:]:  # 跳过 "List of devices attached" 行
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]
        return None
    except Exception:
        return None


ADB_DEVICE = get_adb_device()

# 所有已知的内置接口 URL（auto 模式初始化 seen_uris 用）
KNOWN_API_URLS = {
    f"{BASE_URL}/mp/user/info",
    f"{BASE_URL}/mp/user/myClubs",
    f"{BASE_URL}/mp/user/saveDefaultClub",
    f"{BASE_URL}/mp/oauth/wechatLogin",
    f"{BASE_URL}/mobile/getUserBoxStatus",
    f"{BASE_URL}/mp/record/deviceOnlineInfo",
    f"{BASE_URL}/mobile/loginBoxAfterScanningQrCode",
    f"{BASE_URL}/mp/app/version/check",
    f"{BASE_URL}/mp/coupon/checkEligibility",
    f"{BASE_URL}/mp/coupon/trialList",
    f"{BASE_URL}/video/videoClient/myVideos/readyV2",
    f"{BASE_URL}/video/videoClient/myVideos/failedV2",
    f"{BASE_URL}/mp/record/opponentListWithVideos",
    f"{BASE_URL}/mp/record/opponentStatistics",
    f"{BASE_URL}/mp/record/competitionListWithVideos",
    f"{BASE_URL}/mp/record/inningList",
    f"{BASE_URL}/mp/record/inningStatistics",
    f"{BASE_URL}/video/videoinfo/competitionVideos",
    f"{BASE_URL}/mp/rank/clubList",
    f"{BASE_URL}/mp/rank/userBreakRank",
    f"{BASE_URL}/mp/rank/ratingList",
    f"{BASE_URL}/mp/rank/breakList",
    f"{BASE_URL}/mp/rank/winRateList",
    f"{BASE_URL}/mp/record/barchart",
    f"{BASE_URL}/mp/record/statics",
    f"{BASE_URL}/mp/event/track",
}

# ============== API 记忆库 ==============

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_memory.json")

def load_memory():
    """加载 API 记忆库"""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    """保存 API 记忆库"""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def get_memory_key(uri, method):
    """生成接口的记忆库 key"""
    path = uri.replace(BASE_URL, "")
    return f"{method} {path}"

def add_to_memory(uri, method, data_str, description=""):
    """添加新接口到记忆库"""
    memory = load_memory()
    key = get_memory_key(uri, method)
    if key not in memory:
        # 解析 data
        data = None
        try:
            data = json.loads(data_str)
        except:
            data = _dart_to_json(data_str)
        memory[key] = {
            "url": uri,
            "method": method,
            "path": uri.replace(BASE_URL, ""),
            "data": data,
            "description": description,
            "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_memory(memory)
        return True  # 新增
    return False  # 已存在

# ============== 颜色 ==============

class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def cprint(text, color=None, bold=False):
    prefix = ""
    if bold:
        prefix += Colors.BOLD
    if color:
        prefix += color
    print(f"{prefix}{text}{Colors.RESET}")

# ============== 日志实时查看 ==============

def cmd_log(args):
    """实时查看 App 网络日志"""
    device = getattr(args, '_device', None)
    if not device:
        cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
        return
    pattern = args.pattern or "DIO"
    adb_cmd = ["adb", "-s", device, "logcat"]

    cprint(f"实时日志流 | 过滤: {pattern} | Ctrl+C 停止", Colors.CYAN, bold=True)
    cprint("=" * 60)

    try:
        proc = subprocess.Popen(
            adb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0  # 二进制无缓冲，配合 TextIOWrapper.line_buffering 使用
        )

        import io
        stdout_reader = io.TextIOWrapper(proc.stdout, encoding='utf-8', errors='replace', line_buffering=True)

        for line in stdout_reader:
            if pattern.lower() in line.lower():
                timestamp = line[:19] if len(line) > 19 else ""
                content = line[19:].strip()

                # 根据内容类型着色
                if "*** Request ***" in content:
                    cprint(f"{timestamp} {content}", Colors.GREEN)
                elif "*** Response ***" in content:
                    cprint(f"{timestamp} {content}", Colors.YELLOW)
                elif "uri:" in content:
                    cprint(f"{timestamp} {content}", Colors.BLUE)
                elif "data:" in content or "{" in content:
                    cprint(f"{timestamp} {content}", Colors.WHITE)
                elif "DioException" in content:
                    cprint(f"{timestamp} {content}", Colors.RED)
                else:
                    print(f"{timestamp} {content}")

    except KeyboardInterrupt:
        cprint("\n已停止", Colors.DIM)
    finally:
        proc.terminate()


# ============== 从日志文件提取接口 ==============

def cmd_extract(args):
    """从日志文件提取所有 API 接口"""
    log_file = args.file
    if not os.path.exists(log_file):
        cprint(f"文件不存在: {log_file}", Colors.RED)
        return

    cprint(f"分析日志文件: {log_file}", Colors.CYAN, bold=True)
    cprint("=" * 60)

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 提取所有请求块
    request_pattern = re.compile(
        r'\*\*\* Request \*\*\*.*?'
        r'uri:\s*(https?://\S+).*?'
        r'method:\s*(\w+).*?'
        r'data:\s*\n.*?\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
        re.DOTALL
    )

    # 逐行解析，更健壮
    apis = OrderedDict()
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        if "*** Request ***" in line:
            uri = method = None
            data_lines = []

            # 往后读取请求块（最多 30 行）
            j = i + 1
            while j < min(i + 30, len(lines)):
                l = lines[j]
                # 遇到下一个 Request 或 Response 就停止
                if "*** Request ***" in l or "*** Response ***" in l:
                    break

                if uri is None and "uri:" in l and "https://" in l:
                    m = re.search(r'uri:\s*(https?://\S+)', l)
                    if m:
                        uri = m.group(1).strip()

                if method is None and "method:" in l:
                    m = re.search(r'method:\s*(\w+)', l)
                    if m:
                        method = m.group(1).strip()

                # 收集 data 行
                if "data:" in l and "{" in l:
                    # data 和 JSON 在同一行
                    m = re.search(r'data:\s*(\{.*\})', l)
                    if m:
                        data_lines.append(m.group(1))
                elif "data:" in l:
                    # data 在下一行
                    pass
                elif data_lines is not None and "{" in l and uri and method:
                    # 可能是 data JSON 行
                    stripped = l.split("flutter : [DIO]")[-1].strip() if "flutter" in l else l.strip()
                    if stripped.startswith("{") or stripped.startswith('"'):
                        data_lines.append(stripped)

                j += 1

            if uri and method:
                path = uri.replace(BASE_URL, "")
                key = f"{method} {path}"

                # 合并并解析 data
                raw_data = " ".join(data_lines) if data_lines else ""
                try:
                    parsed_data = json.loads(raw_data) if raw_data else {}
                except:
                    # 尝试去掉非 JSON 部分
                    m = re.search(r'(\{.*\})', raw_data)
                    try:
                        parsed_data = json.loads(m.group(1)) if m else {}
                    except:
                        parsed_data = {"raw": raw_data[:200]}

                if key not in apis:
                    apis[key] = {
                        "url": uri,
                        "method": method,
                        "data": parsed_data,
                    }

            i = j
        else:
            i += 1

    # 输出结果
    cprint(f"\n共发现 {len(apis)} 个接口:\n", Colors.GREEN, bold=True)

    for idx, (key, api) in enumerate(apis.items(), 1):
        cprint(f"  {idx}. {key}", Colors.BOLD)
        cprint(f"     URL: {api['url']}", Colors.DIM)
        if api["data"]:
            data_str = json.dumps(api["data"], ensure_ascii=False, indent=6)
            cprint(f"     Data: {data_str}", Colors.DIM)
        print()

    # 保存为 JSON
    if args.save:
        output_file = args.save
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(apis, f, ensure_ascii=False, indent=2)
        cprint(f"已保存到: {output_file}", Colors.GREEN)


# ============== 调用指定接口 ==============

def cmd_call(args):
    """调用指定接口并显示完整响应"""

    # 预定义的快捷接口（26 个，全部从记忆库同步）
    presets = {
        # ---- 用户 ----
        "user": {
            "name": "获取用户信息",
            "method": "POST",
            "url": f"{BASE_URL}/mp/user/info",
            "data": {"userId": USER_ID}
        },
        "myClubs": {
            "name": "我的俱乐部",
            "method": "POST",
            "url": f"{BASE_URL}/mp/user/myClubs",
            "data": {"userId": USER_ID}
        },
        "saveDefaultClub": {
            "name": "保存默认俱乐部",
            "method": "POST",
            "url": f"{BASE_URL}/mp/user/saveDefaultClub",
            "data": {"clubId": 45376, "userId": USER_ID}
        },
        "wechatLogin": {
            "name": "微信登录",
            "method": "POST",
            "url": f"{BASE_URL}/mp/oauth/wechatLogin",
            "data": None
        },
        # ---- 设备 ----
        "box": {
            "name": "获取盒子状态",
            "method": "POST",
            "url": f"{BASE_URL}/mobile/getUserBoxStatus",
            "data": {"userId": USER_ID}
        },
        "deviceOnline": {
            "name": "设备在线状态",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/deviceOnlineInfo",
            "data": {"competitionId": "bf0442cd43214739a799233bc4852738", "userId": USER_ID}
        },
        "loginBox": {
            "name": "扫码绑定盒子",
            "method": "POST",
            "url": f"{BASE_URL}/mobile/loginBoxAfterScanningQrCode",
            "data": {"encryptedString": "http://weixin.qq.com/q/02AYDNBsWOf9E1JX0n1GcW", "userId": USER_ID}
        },
        # ---- 版本 ----
        "version": {
            "name": "检查版本",
            "method": "POST",
            "url": f"{BASE_URL}/mp/app/version/check",
            "data": {"platform": 2, "currentVersion": "1.0.0", "userId": USER_ID}
        },
        # ---- 视频券 ----
        "coupon": {
            "name": "检查视频券",
            "method": "POST",
            "url": f"{BASE_URL}/mp/coupon/checkEligibility",
            "data": {"userId": USER_ID}
        },
        "trial": {
            "name": "试用券列表",
            "method": "POST",
            "url": f"{BASE_URL}/mp/coupon/trialList",
            "data": {"pageNo": 1, "pageSize": 100, "status": 0, "userId": USER_ID}
        },
        # ---- 视频 ----
        "readyV2": {
            "name": "待制作视频",
            "method": "POST",
            "url": f"{BASE_URL}/video/videoClient/myVideos/readyV2",
            "data": {"pageNo": 1, "pageSize": 10, "clientId": "BP2A.250605.031.A3_V000L1", "userId": USER_ID}
        },
        "failedV2": {
            "name": "制作失败视频",
            "method": "POST",
            "url": f"{BASE_URL}/video/videoClient/myVideos/failedV2",
            "data": {"pageNo": 1, "pageSize": 10, "clientId": "BP2A.250605.031.A3_V000L1", "userId": USER_ID}
        },
        # ---- 交手记录 ----
        "matches": {
            "name": "对手列表和视频",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/opponentListWithVideos",
            "data": {"userId": USER_ID}
        },
        "stats": {
            "name": "对手统计数据",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/opponentStatistics",
            "data": {"userId": USER_ID, "startTime": "2026-08-03 00:00:00", "endTime": "2026-08-09 23:59:59"}
        },
        "competitionList": {
            "name": "比赛列表和视频",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/competitionListWithVideos",
            "data": {"userA": USER_ID, "userB": "aff7eae4-3680-4b89-9f01-819e02c3b6b5", "startTime": "2026-08-03 00:00:00", "endTime": "2026-08-09 23:59:59", "page": 1, "pageSize": 10, "userId": USER_ID}
        },
        "inningList": {
            "name": "局列表",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/inningList",
            "data": {"competitionId": "fecd7c799ea5495ca23caceafaaca04b", "userId": USER_ID}
        },
        "inningStatistics": {
            "name": "局统计",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/inningStatistics",
            "data": {"competitionId": "bf0442cd43214739a799233bc4852738", "userId": USER_ID}
        },
        "competitionVideos": {
            "name": "场比赛视频",
            "method": "POST",
            "url": f"{BASE_URL}/video/videoinfo/competitionVideos",
            "data": {"competitionId": "fecd7c799ea5495ca23caceafaaca04b", "userId": USER_ID}
        },
        # ---- 排行榜 ----
        "clubList": {
            "name": "俱乐部排行榜",
            "method": "POST",
            "url": f"{BASE_URL}/mp/rank/clubList",
            "data": {"userId": USER_ID}
        },
        "userBreakRank": {
            "name": "用户破分榜",
            "method": "POST",
            "url": f"{BASE_URL}/mp/rank/userBreakRank",
            "data": {"rankRange": None, "timeRange": None, "merchantAddressId": None, "userId": USER_ID}
        },
        "ratingList": {
            "name": "评级榜",
            "method": "POST",
            "url": f"{BASE_URL}/mp/rank/ratingList",
            "data": {"type": 3, "merchantAddressId": 45376, "areaId": None, "userId": USER_ID}
        },
        "breakList": {
            "name": "破分榜",
            "method": "POST",
            "url": f"{BASE_URL}/mp/rank/breakList",
            "data": {"type": 0, "merchantAddressId": 45376, "areaId": None, "rankRange": 0, "timeRange": 0, "userId": USER_ID}
        },
        "winRateList": {
            "name": "胜率榜",
            "method": "POST",
            "url": f"{BASE_URL}/mp/rank/winRateList",
            "data": {"type": 2, "merchantAddressId": 45376, "areaId": None, "rankRange": 0, "timeRange": 0, "userId": USER_ID}
        },
        # ---- 数据统计 ----
        "barchart": {
            "name": "柱状图统计",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/barchart",
            "data": {"userId": USER_ID, "startTime": "2026-08-03 00:00:00", "endTime": "2026-08-09 23:59:59"}
        },
        "statics": {
            "name": "综合统计",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/statics",
            "data": {"userId": USER_ID, "startTime": "2026-08-03 00:00:00", "endTime": "2026-08-09 23:59:59"}
        },
        # ---- 埋点 ----
        "track": {
            "name": "埋点上报",
            "method": "POST",
            "url": f"{BASE_URL}/mp/event/track",
            "data": {"modelType": 1, "eventType": 5, "attrName": "me", "attrValue": None, "clientType": 1, "userId": USER_ID}
        },
    }

    if args.name in presets:
        api = presets[args.name]
    elif args.url:
        api = {
            "name": args.name or args.url,
            "method": "POST",
            "url": args.url,
            "data": json.loads(args.data) if args.data else {"userId": USER_ID}
        }
    else:
        # 尝试从记忆库查找
        memory = load_memory()
        if args.name in memory:
            api = memory[args.name]
            api["name"] = args.name
        else:
            cprint(f"未知接口: {args.name}", Colors.RED)
            cprint(f"\n内置快捷名称: {', '.join(presets.keys())}", Colors.YELLOW)
            if memory:
                cprint(f"记忆库接口: {', '.join(memory.keys())}", Colors.YELLOW)
            return

    cprint(f"\n调用: {api['name']}", Colors.CYAN, bold=True)
    cprint(f"URL: {api['url']}", Colors.BLUE)
    cprint(f"Method: {api['method']}", Colors.BLUE)
    cprint(f"Data: {json.dumps(api['data'], ensure_ascii=False)}", Colors.DIM)
    cprint("-" * 60)

    try:
        start = time.time()
        resp = requests.post(
            api["url"],
            json=api["data"],
            headers=HEADERS,
            timeout=10,
            proxies={"http": None, "https": None}  # 禁用代理
        )
        elapsed = time.time() - start

        cprint(f"Status: {resp.status_code} ({elapsed*1000:.0f}ms)", Colors.GREEN if resp.status_code == 200 else Colors.RED)

        # 格式化输出
        try:
            result = resp.json()
            formatted = json.dumps(result, ensure_ascii=False, indent=2)
            cprint(f"\n{formatted}", Colors.WHITE)
        except:
            cprint(f"\n{resp.text}", Colors.WHITE)

        # 简单分析
        if resp.status_code == 200:
            try:
                result = resp.json()
                code = result.get("code", -1)
                msg = result.get("msg", "")
                data = result.get("data")

                cprint(f"\n--- 快速分析 ---", Colors.YELLOW)
                cprint(f"code: {code} | msg: {msg}", Colors.GREEN if code == 0 else Colors.RED)

                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, str) and len(v) > 60:
                            v = v[:60] + "..."
                        cprint(f"  {k}: {v}", Colors.DIM)
                elif isinstance(data, list):
                    cprint(f"  列表长度: {len(data)}", Colors.DIM)
                    if data and isinstance(data[0], dict):
                        cprint(f"  首条记录 keys: {list(data[0].keys())}", Colors.DIM)
            except:
                pass

    except requests.exceptions.RequestException as e:
        cprint(f"请求失败: {e}", Colors.RED)


# ============== 列出所有接口 ==============

def cmd_list(args):
    """列出所有已知接口"""
    presets = {
        "user": "POST /mp/user/info - 获取用户信息",
        "myClubs": "POST /mp/user/myClubs - 我的俱乐部",
        "saveDefaultClub": "POST /mp/user/saveDefaultClub - 保存默认俱乐部",
        "wechatLogin": "POST /mp/oauth/wechatLogin - 微信登录",
        "box": "POST /mobile/getUserBoxStatus - 获取盒子状态",
        "deviceOnline": "POST /mp/record/deviceOnlineInfo - 设备在线状态",
        "loginBox": "POST /mobile/loginBoxAfterScanningQrCode - 扫码绑定盒子",
        "version": "POST /mp/app/version/check - 检查版本",
        "coupon": "POST /mp/coupon/checkEligibility - 检查视频券",
        "trial": "POST /mp/coupon/trialList - 试用券列表",
        "readyV2": "POST /video/videoClient/myVideos/readyV2 - 待制作视频",
        "failedV2": "POST /video/videoClient/myVideos/failedV2 - 制作失败视频",
        "matches": "POST /mp/record/opponentListWithVideos - 对手列表和视频",
        "stats": "POST /mp/record/opponentStatistics - 对手统计",
        "competitionList": "POST /mp/record/competitionListWithVideos - 比赛列表和视频",
        "inningList": "POST /mp/record/inningList - 局列表",
        "inningStatistics": "POST /mp/record/inningStatistics - 局统计",
        "competitionVideos": "POST /video/videoinfo/competitionVideos - 场比赛视频",
        "clubList": "POST /mp/rank/clubList - 俱乐部排行榜",
        "userBreakRank": "POST /mp/rank/userBreakRank - 用户破分榜",
        "ratingList": "POST /mp/rank/ratingList - 评级榜",
        "breakList": "POST /mp/rank/breakList - 破分榜",
        "winRateList": "POST /mp/rank/winRateList - 胜率榜",
        "barchart": "POST /mp/record/barchart - 柱状图统计",
        "statics": "POST /mp/record/statics - 综合统计",
        "track": "POST /mp/event/track - 埋点上报"
    }

    memory = load_memory()

    cprint("  内置接口:", Colors.CYAN, bold=True)
    for key, desc in presets.items():
        cprint(f"    {key:10s} {desc}", Colors.WHITE)

    if memory:
        cprint(f"\n  记忆库接口 ({len(memory)} 个):", Colors.YELLOW, bold=True)
        for key, api in memory.items():
            desc = api.get("description", "")
            discovered = api.get("discovered_at", "")
            cprint(f"    {key:50s} {desc}", Colors.WHITE)
            cprint(f"    {'':50s} 发现于: {discovered}", Colors.DIM)
    else:
        cprint(f"\n  记忆库接口: (空)", Colors.DIM)

    cprint(f"\n调用示例: python api_tool.py call user", Colors.DIM)
    cprint(f"           python api_tool.py call -u /mp/record/xxx  (调用记忆库中的接口)", Colors.DIM)


# ============== 自动模式 ==============

def _fetch_full_response(uri, method, data_str):
    """用 Python requests 获取完整响应（绕过 logcat 截断）"""
    data = None
    try:
        data = json.loads(data_str)
    except:
        data = _dart_to_json(data_str)
    if data is None:
        data = {"raw": data_str[:200]}

    try:
        resp = requests.post(uri, json=data, headers=HEADERS, timeout=10, proxies={"http": None, "https": None})
        if resp.status_code == 200:
            try:
                return resp.json()
            except:
                return {"raw": resp.text[:500]}
        else:
            return {"_error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"_error": str(e)}


def _display_request_response(uri, method, data_lines, response_lines, seen_uris, discovered_apis, is_error=False, full_data=None, device_tag=""):
    """显示一个完整的请求+响应（full_data 为 Python requests 拿到的完整响应）"""
    # 解析 data
    data_str = " ".join(data_lines)
    data = None
    try:
        data = json.loads(data_str)
    except:
        data = _dart_to_json(data_str)
    if data is None:
        data = {"raw": data_str[:200]}

    # 优先使用 Python requests 的完整响应，否则用 logcat 的截断响应
    response_data = full_data
    response_text = ""
    if response_data is None:
        response_text = " ".join(response_lines).strip()
        try:
            response_data = json.loads(response_text)
        except:
            response_data = None

    # 实时更新 Token
    # 显示
    is_new = uri not in seen_uris
    if is_new:
        seen_uris.add(uri)
        discovered_apis.append({"uri": uri, "method": method, "data": data_str})

    path = uri.replace(BASE_URL, "")
    marker = " [NEW]" if is_new else ""
    prefix = f"[{device_tag}] " if device_tag else ""

    print()  # 空行分隔
    if is_error:
        cprint(f"{prefix}!! {method} {path}{marker}", Colors.RED, bold=True)
    elif is_new:
        cprint(f"{prefix}>> {method} {path}{marker}", Colors.GREEN, bold=True)
    else:
        cprint(f"{prefix}>> {method} {path}", Colors.BLUE)

    # 请求参数
    if data and data != {"raw": ""}:
        data_display = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)
        cprint(f"{prefix}   请求: {data_display}", Colors.DIM)

    # 响应体
    if response_data:
        if "_error" in response_data:
            cprint(f"{prefix}   响应: (requests调用失败: {response_data['_error']})", Colors.RED)
        else:
            source_tag = " [requests]" if full_data else " [logcat]"
            resp_display = json.dumps(response_data, ensure_ascii=False, indent=2)
            cprint(f"{prefix}   响应{source_tag}:\n{resp_display}", Colors.WHITE)
    elif response_text:
        cprint(f"{prefix}   响应: {response_text[:500]}", Colors.WHITE)
    elif is_error:
        cprint(f"{prefix}   响应: (异常/无响应)", Colors.RED)
    else:
        cprint(f"{prefix}   响应: (等待中...)", Colors.DIM)


# 全局打印锁，防止多线程输出交错
_print_lock = threading.Lock()

def _threaded_display_request_response(uri, method, data_lines, response_lines,
                                        seen_uris, discovered_apis, is_error=False,
                                        full_data=None, hide_list=None, device_tag=""):
    """线程安全的显示函数，带打印锁"""
    if hide_list is None:
        hide_list = []
    path = uri.replace(BASE_URL, "")
    if any(h in path for h in hide_list):
        return

    with _print_lock:
        _display_request_response(
            uri, method, data_lines, response_lines,
            seen_uris, discovered_apis, is_error, full_data, device_tag
        )


def _short_device_id(device):
    """缩短设备ID用于显示标签"""
    if device.startswith("adb-"):
        # WiFi设备: adb-IVXGSGRKEATKXO4D-xxx -> IVXGSGRK
        parts = device.split("-")
        return parts[1][:8] if len(parts) >= 2 else device[:10]
    return device[:8]  # USB设备取前8位


def cmd_auto(args):
    """实时监控 + 自动发现新接口（支持多设备并行）"""
    devices = getattr(args, '_devices', None)
    if not devices:
        cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
        return

    full_mode = getattr(args, 'full', False)
    hide_list = getattr(args, 'hide', []) or []

    if len(devices) > 1:
        cprint(f"自动监控模式 | {len(devices)} 台设备并行监控", Colors.CYAN, bold=True)
        for d in devices:
            tag = f"[{_short_device_id(d)}]"
            cprint(f"  {tag} {d}", Colors.DIM)
    else:
        cprint(f"自动监控模式 | 设备: {devices[0]}", Colors.CYAN, bold=True)

    if full_mode:
        cprint("模式: logcat 监听 + Python requests 获取完整响应（并行）", Colors.CYAN)
    else:
        cprint("模式: logcat 监听（大响应可能被截断）", Colors.CYAN)

    if hide_list:
        cprint(f"已隐藏接口: {', '.join(hide_list)}", Colors.DIM)
    cprint("Ctrl+C 停止", Colors.DIM)
    cprint("=" * 60)

    # 初始化 known_uris：内置接口 + 记忆库接口，这些不会标记为 [NEW]
    known_uris = set(KNOWN_API_URLS)
    memory = load_memory()
    for api in memory.values():
        known_uris.add(api["url"])

    # 共享状态用锁保护
    state_lock = threading.Lock()
    seen_uris = set(known_uris)
    discovered_apis = []
    request_count = [0]

    # 每个设备独立的请求队列
    stop_event = threading.Event()
    worker_threads = []

    def make_worker(device_id, request_q):
        """为每个设备创建一个工作线程（--full模式下调用Python requests）"""
        def worker():
            while not stop_event.is_set():
                try:
                    item = request_q.get(timeout=0.5)
                except queue.Empty:
                    continue

                uri, method, data_lines, response_lines = item

                full_data = None
                if full_mode and data_lines:
                    full_data = _fetch_full_response(uri, method, " ".join(data_lines))
                    if full_data and "_error" in full_data:
                        with _print_lock:
                            cprint(f"  [{_short_device_id(device_id)}] requests调用失败: {full_data['_error']}", Colors.DIM)

                _threaded_display_request_response(
                    uri, method, data_lines, response_lines,
                    seen_uris, discovered_apis,
                    full_data=full_data, hide_list=hide_list,
                    device_tag=_short_device_id(device_id),
                )

                # 自动存入记忆库
                with state_lock:
                    if uri not in known_uris:
                        added = add_to_memory(uri, method, " ".join(data_lines))
                        if added:
                            with _print_lock:
                                cprint(f"  [{_short_device_id(device_id)}] 💾 已存入记忆库: {method} {uri.replace(BASE_URL, '')}", Colors.DIM)
                        seen_uris.add(uri)
                        discovered_apis.append({"uri": uri, "method": method, "data": " ".join(data_lines)})
                    request_count[0] += 1

                request_q.task_done()
        return worker

    # 为每个设备创建请求队列和工作线程
    device_queues = {}
    for device_id in devices:
        q = queue.Queue()
        device_queues[device_id] = q

        if full_mode:
            wt = threading.Thread(target=make_worker(device_id, q), daemon=True)
            wt.start()
            worker_threads.append(wt)

    def process_line(device_id, content, request_q, buf):
        """处理一行 logcat 输出，解析DIO请求/响应"""
        if "*** Request ***" in content:
            if buf["uri"]:
                request_q.put((
                    buf["uri"], buf["method"],
                    buf["data_lines"][:], buf["response_lines"][:]
                ))
            buf["uri"] = None
            buf["method"] = None
            buf["data_lines"] = []
            buf["auth"] = None
            buf["refresh"] = None
            buf["response_lines"] = []
            buf["in_data"] = False
            buf["in_response"] = False

        elif "*** Response ***" in content:
            buf["in_response"] = "headers"
            buf["response_lines"] = []

        elif "*** DioException ***" in content:
            if buf["uri"]:
                request_q.put((
                    buf["uri"], buf["method"],
                    buf["data_lines"][:], buf["response_lines"][:]
                ))
            buf["uri"] = None
            buf["in_response"] = False

        elif buf["in_response"] == "headers" and "Response Text:" in content:
            buf["in_response"] = "body"
            after_marker = content.split("Response Text:")[-1].strip()
            if after_marker and "[DIO]" not in after_marker:
                buf["response_lines"].append(after_marker)
        elif buf["in_response"] == "body" and content:
            if "[DIO]" in content:
                after_dio = content.split("[DIO]")[-1].strip()
                if after_dio and not after_dio.startswith("***"):
                    buf["response_lines"].append(after_dio)
            else:
                buf["in_response"] = False

        elif "uri:" in content and "https://" in content:
            m = re.search(r'uri:\s*(https?://\S+)', content)
            if m:
                buf["uri"] = m.group(1).strip()

        elif "method:" in content:
            m = re.search(r'method:\s*(\w+)', content)
            if m:
                buf["method"] = m.group(1).strip()

        elif "Authorization:" in content:
            m = re.search(r'Authorization:\s*(\S+)', content)
            if m:
                buf["auth"] = m.group(1).strip()

        elif "refresh_token:" in content:
            m = re.search(r'refresh_token:\s*(\S+)', content)
            if m:
                buf["refresh"] = m.group(1).strip()

        elif "data:" in content:
            buf["in_data"] = True
            buf["data_lines"] = []
            after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
            if "{" in after_dio and after_dio != "data:":
                buf["data_lines"].append(after_dio.replace("data:", "").strip())

        elif buf["in_data"]:
            after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
            if "*** " in after_dio or after_dio == "":
                buf["in_data"] = False
            elif after_dio and ("{" in after_dio or after_dio.startswith('"') or ":" in after_dio):
                buf["data_lines"].append(after_dio)

    def logcat_reader(device_id):
        """为单个设备启动 logcat 流，实时解析DIO日志"""
        adb_cmd = ["adb", "-s", device_id, "logcat"]
        tag = _short_device_id(device_id)
        proc = None
        buf = {
            "uri": None, "method": None,
            "data_lines": [], "auth": None, "refresh": None,
            "response_lines": [], "in_data": False, "in_response": False,
        }

        try:
            proc = subprocess.Popen(
                adb_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )

            import io
            stdout_reader = io.TextIOWrapper(proc.stdout, encoding='utf-8', errors='replace', line_buffering=True)

            for line in stdout_reader:
                if stop_event.is_set():
                    break
                content = line.strip()
                request_q = device_queues.get(device_id)
                if request_q:
                    process_line(device_id, content, request_q, buf)

        except Exception as e:
            with _print_lock:
                cprint(f"  [{tag}] logcat错误: {e}", Colors.RED)
        finally:
            # 最后一个请求丢入队列
            if buf["uri"]:
                request_q = device_queues.get(device_id)
                if request_q:
                    request_q.put((
                        buf["uri"], buf["method"],
                        buf["data_lines"][:], buf["response_lines"][:]
                    ))
            if proc:
                proc.terminate()

    # 为每个设备启动 logcat 读取线程
    logcat_threads = []
    for device_id in devices:
        t = threading.Thread(target=logcat_reader, args=(device_id,), daemon=True)
        t.start()
        logcat_threads.append(t)

    try:
        # 主线程等待，直到 Ctrl+C
        while True:
            time.sleep(1)
            alive = any(t.is_alive() for t in logcat_threads)
            if not alive:
                cprint("\n所有设备 logcat 流已断开", Colors.DIM)
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()

        # 等待工作线程处理完
        for q in device_queues.values():
            try:
                q.join(timeout=3)
            except:
                pass
        for wt in worker_threads:
            wt.join(timeout=5)

        cprint(f"\n已停止，共捕获 {request_count[0]} 个请求，发现 {len(seen_uris) - len(known_uris)} 个新接口", Colors.DIM)
        if discovered_apis:
            cprint("\n发现的接口列表:", Colors.YELLOW, bold=True)
            for api in discovered_apis:
                cprint(f"  {api['method']} {api['uri'].replace(BASE_URL, '')}", Colors.WHITE)
            cprint(f"\n提示: 将新接口添加到 api_tool.py 的 presets 中即可用 call 命令调用", Colors.DIM)


def _dart_to_json(dart_str):
    """将 Dart 风格对象转为 JSON（{key: value} → {"key": "value"}）"""
    if not dart_str or not dart_str.strip().startswith("{"):
        return None
    s = dart_str.strip()
    # 去掉外层 {}
    inner = s[1:-1].strip() if s.endswith("}") else s[1:].strip()
    if not inner:
        return {}

    result = {}
    # 按逗号分割，但要处理嵌套 {}
    parts = []
    depth = 0
    current = ""
    for ch in inner:
        if ch == "{":
            depth += 1
            current += ch
        elif ch == "}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())

    for part in parts:
        if ":" in part:
            key, _, value = part.partition(":")
            key = key.strip()
            value = value.strip()
            # 判断值类型
            if value == "null":
                result[key] = None
            elif value == "true":
                result[key] = True
            elif value == "false":
                result[key] = False
            elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                result[key] = int(value)
            elif "." in value:
                try:
                    result[key] = float(value)
                except:
                    result[key] = value
            else:
                result[key] = value
    return result


def _handle_new_api(uri, method, data_lines):
    """处理新发现的接口"""
    data_str = " ".join(data_lines)

    # 尝试解析：先标准 JSON，再 Dart 格式
    data = None
    try:
        data = json.loads(data_str)
    except:
        data = _dart_to_json(data_str)
    if data is None:
        data = {"raw": data_str}

    cprint(f"\n{'=' * 60}", Colors.CYAN)
    cprint(f"发现新接口! {method} {uri.replace(BASE_URL, '')}", Colors.GREEN, bold=True)
    cprint(f"Data: {json.dumps(data, ensure_ascii=False)}", Colors.DIM)

    # 自动调用获取完整响应
    try:
        resp = requests.post(uri, json=data, headers=HEADERS, timeout=10, proxies={"http": None, "https": None})
        cprint(f"Status: {resp.status_code}", Colors.GREEN if resp.status_code == 200 else Colors.RED)

        try:
            result = resp.json()
            formatted = json.dumps(result, ensure_ascii=False, indent=2)
            # 截断过长的输出
            if len(formatted) > 2000:
                formatted = formatted[:2000] + "\n... (响应过长已截断)"
            cprint(f"Response:\n{formatted}", Colors.WHITE)
        except:
            cprint(f"Response: {resp.text[:500]}", Colors.WHITE)
    except Exception as e:
        cprint(f"调用失败: {e}", Colors.RED)


# ============== CLI ==============

def main():
    parser = argparse.ArgumentParser(
        description="斯诺克大师 App API 抓包调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python api_tool.py log                    # 实时查看日志
  python api_tool.py log -p "uri:"          # 只看 URL
  python api_tool.py extract app_log.txt    # 从日志文件提取接口
  python api_tool.py call user              # 调用用户信息接口
  python api_tool.py call matches           # 调用对手列表接口
  python api_tool.py call -u https://...    # 调用自定义 URL
  python api_tool.py auto                   # 实时监控 + 自动发现
  python api_tool.py auto --full            # 自动发现 + Python requests 拿完整响应
  python api_tool.py auto -s 设备ID --full  # 指定设备 + 完整响应
  python api_tool.py list                   # 列出所有已知接口
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # log
    log_parser = subparsers.add_parser("log", help="实时查看 App 网络日志")
    log_parser.add_argument("-s", "--device", help="指定 ADB 设备 ID（多设备时必须指定）")
    log_parser.add_argument("-p", "--pattern", help="过滤关键词 (默认: DIO)")

    # extract
    ext_parser = subparsers.add_parser("extract", help="从日志文件提取接口")
    ext_parser.add_argument("file", help="日志文件路径")
    ext_parser.add_argument("-s", "--save", help="保存为 JSON 文件")

    # call
    call_parser = subparsers.add_parser("call", help="调用指定接口")
    call_parser.add_argument("name", nargs="?", help="接口快捷名称 (user/box/version/coupon/trial/matches/stats/track)")
    call_parser.add_argument("-u", "--url", help="自定义接口 URL")
    call_parser.add_argument("-d", "--data", help="自定义请求数据 (JSON)")

    # auto
    auto_parser = subparsers.add_parser("auto", help="实时监控 + 自动发现接口")
    auto_parser.add_argument("-s", "--device", nargs="+", default=None,
        help="指定 ADB 设备 ID（支持多个设备，空格分隔）")
    auto_parser.add_argument("--hide", nargs="+", default=[
        "/mobile/getUserBoxStatus",
        "/mp/user/info",
    ], help="隐藏高频轮询接口路径 (默认隐藏 getUserBoxStatus 和 user/info)")
    auto_parser.add_argument("--full", action="store_true",
        help="自动用 Python requests 调用每个请求获取完整响应（绕过 logcat 截断限制）")

    # list
    list_parser = subparsers.add_parser("list", help="列出所有已知接口")

    args = parser.parse_args()

    # 处理 -s 设备参数
    device = None  # 用于 log/call 等单设备命令
    devices = None  # 用于 auto 多设备命令

    if args.command == "auto":
        if args.device:
            devices = args.device  # nargs="+" 返回 list
            for d in devices:
                cprint(f"指定设备: {d}", Colors.CYAN)
        else:
            # 未指定设备时，自动获取所有已连接设备
            all_devices = []
            try:
                result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                for line in result.stdout.strip().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        all_devices.append(parts[0])
            except:
                pass
            if all_devices:
                devices = all_devices
            else:
                devices = [ADB_DEVICE] if ADB_DEVICE else None

        args._devices = devices
    else:
        # 其他命令：单设备逻辑
        if hasattr(args, 'device') and args.device:
            device = args.device
            cprint(f"指定设备: {device}", Colors.CYAN)
        else:
            device = ADB_DEVICE

    if args.command == "log":
        args._device = device
        cmd_log(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "call":
        cmd_call(args)
    elif args.command == "auto":
        if not args._devices:
            cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
            sys.exit(1)
        cmd_auto(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
