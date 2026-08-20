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
import io
import requests
from datetime import datetime
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

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
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


ADB_DEVICE = get_adb_device()


# ============== API 记忆库（线程安全 + 缓存） ==============

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_memory.json")


class MemoryManager:
    """线程安全的 API 记忆库管理器，内存缓存 + 定期批量写入"""

    def __init__(self, filepath):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._cache = self._load()
        self._dirty = False
        # 后台定期保存线程（daemon 模式，主线程退出时自动终止）
        self._save_timer = threading.Timer(30.0, self._periodic_save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _load(self):
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_unlocked(self):
        """内部保存方法，调用者必须已持有 self._lock"""
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except OSError:
            pass

    def _periodic_save(self):
        """定期保存（后台线程）"""
        try:
            with self._lock:
                if self._dirty:
                    self._save_unlocked()
        except Exception:
            pass
        # 重新启动定时器
        try:
            self._save_timer = threading.Timer(30.0, self._periodic_save)
            self._save_timer.daemon = True
            self._save_timer.start()
        except RuntimeError:
            pass  # Python 解释器正在关闭

    def flush(self):
        """强制保存所有未写入的数据"""
        with self._lock:
            if self._dirty:
                self._save_unlocked()

    def shutdown(self):
        """关闭管理器，停止定时保存"""
        try:
            self._save_timer.cancel()
        except Exception:
            pass
        self.flush()

    def get(self):
        with self._lock:
            return dict(self._cache)

    def get_key(self, uri, method):
        path = uri.replace(BASE_URL, "")
        return f"{method} {path}"

    def add(self, uri, method, data_str, description=""):
        """添加新接口到记忆库，线程安全，返回 True 表示新增"""
        key = self.get_key(uri, method)
        with self._lock:
            if key in self._cache:
                return False
            data = None
            try:
                data = json.loads(data_str)
            except (json.JSONDecodeError, ValueError):
                data = _dart_to_json(data_str)
            self._cache[key] = {
                "url": uri,
                "method": method,
                "path": uri.replace(BASE_URL, ""),
                "data": data,
                "description": description,
                "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._dirty = True
            # 立即写入（auto 模式发现新接口时用户会立即看到反馈）
            self._save_unlocked()
            return True

    def known_urls(self):
        with self._lock:
            return {api["url"] for api in self._cache.values()}


# 全局记忆库实例
_memory_mgr = MemoryManager(MEMORY_FILE)


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


# 全局打印锁，防止多线程输出交错
_print_lock = threading.Lock()


def safe_print(text, color=None, bold=False):
    """线程安全的打印：先在锁外格式化，再在锁内打印"""
    prefix = ""
    if bold:
        prefix += Colors.BOLD
    if color:
        prefix += color
    formatted = f"{prefix}{text}{Colors.RESET}"
    with _print_lock:
        print(formatted)


# ============== 接口解析工具 ==============

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
            if value == "null":
                result[key] = None
            elif value == "true":
                result[key] = True
            elif value == "false":
                result[key] = False
            elif value.lstrip("-").isdigit():
                result[key] = int(value)
            elif "." in value:
                try:
                    result[key] = float(value)
                except ValueError:
                    result[key] = value
            else:
                result[key] = value
    return result


def _parse_request_data(data_lines):
    """解析请求数据，先尝试标准 JSON，再尝试 Dart 格式"""
    data_str = " ".join(data_lines).strip()
    if not data_str:
        return {}, data_str
    try:
        return json.loads(data_str), data_str
    except (json.JSONDecodeError, ValueError):
        parsed = _dart_to_json(data_str)
        if parsed is not None:
            return parsed, data_str
        return {"raw": data_str[:200]}, data_str


def _fetch_full_response(uri, method, data_str):
    """用 Python requests 获取完整响应（绕过 logcat 截断）"""
    data = None
    try:
        data = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        data = _dart_to_json(data_str)
    if data is None:
        data = {"raw": data_str[:200]}

    try:
        resp = requests.post(uri, json=data, headers=HEADERS, timeout=10, proxies={"http": None, "https": None})
        if resp.status_code == 200:
            try:
                return resp.json()
            except (json.JSONDecodeError, ValueError):
                return {"raw": resp.text[:500]}
        else:
            return {"_error": f"HTTP {resp.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"_error": str(e)}


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
            bufsize=0
        )

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

    # 逐行解析
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
                    m = re.search(r'data:\s*(\{.*\})', l)
                    if m:
                        data_lines.append(m.group(1))
                elif data_lines is not None and "{" in l and uri and method:
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
                except (json.JSONDecodeError, ValueError):
                    m = re.search(r'(\{.*\})', raw_data)
                    try:
                        parsed_data = json.loads(m.group(1)) if m else {}
                    except (json.JSONDecodeError, ValueError):
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

    # 预定义的快捷接口
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
        memory = _memory_mgr.get()
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
            proxies={"http": None, "https": None}
        )
        elapsed = time.time() - start

        cprint(f"Status: {resp.status_code} ({elapsed*1000:.0f}ms)", Colors.GREEN if resp.status_code == 200 else Colors.RED)

        # 格式化输出
        try:
            result = resp.json()
            formatted = json.dumps(result, ensure_ascii=False, indent=2)
            cprint(f"\n{formatted}", Colors.WHITE)
        except (json.JSONDecodeError, ValueError):
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
            except (json.JSONDecodeError, ValueError):
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

    memory = _memory_mgr.get()

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


# ============== 自动模式（重构版） ==============

def _short_device_id(device):
    """缩短设备ID用于显示标签"""
    if device.startswith("adb-"):
        parts = device.split("-")
        return parts[1][:8] if len(parts) >= 2 else device[:10]
    return device[:8]


def cmd_auto(args):
    """实时监控 + 自动发现新接口（支持多设备并行）"""
    devices = getattr(args, '_devices', None)
    if not devices:
        cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
        return

    full_mode = getattr(args, 'full', False)
    hide_list = getattr(args, 'hide', []) or []

    # 显示模式信息
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

    # 初始化 known_uris：内置接口 + 记忆库接口
    known_urls = set()
    # 内置接口路径（从 presets 提取）
    builtin_paths = {
        "/mp/user/info", "/mp/user/myClubs", "/mp/user/saveDefaultClub",
        "/mp/oauth/wechatLogin", "/mobile/getUserBoxStatus",
        "/mp/record/deviceOnlineInfo", "/mobile/loginBoxAfterScanningQrCode",
        "/mp/app/version/check", "/mp/coupon/checkEligibility",
        "/mp/coupon/trialList", "/video/videoClient/myVideos/readyV2",
        "/video/videoClient/myVideos/failedV2", "/mp/record/opponentListWithVideos",
        "/mp/record/opponentStatistics", "/mp/record/competitionListWithVideos",
        "/mp/record/inningList", "/mp/record/inningStatistics",
        "/video/videoinfo/competitionVideos", "/mp/rank/clubList",
        "/mp/rank/userBreakRank", "/mp/rank/ratingList", "/mp/rank/breakList",
        "/mp/rank/winRateList", "/mp/record/barchart", "/mp/record/statics",
        "/mp/event/track",
    }
    known_urls = {f"{BASE_URL}{p}" for p in builtin_paths}
    known_urls.update(_memory_mgr.known_urls())

    # 共享状态
    state_lock = threading.Lock()
    seen_uris = set(known_urls)  # 已处理过的 URI（不标记 [NEW]）
    discovered_apis = []         # 新发现的接口列表
    request_count = [0]          # 总请求计数

    # 请求队列（logcat → HTTP worker）
    request_q = queue.Queue()
    # 显示队列（HTTP worker → 显示线程）
    display_q = queue.Queue()

    stop_event = threading.Event()

    # ============ HTTP Worker（线程池，并行获取响应） ============

    def http_worker():
        """从请求队列取请求，并行获取完整响应，结果放入显示队列"""
        while not stop_event.is_set():
            try:
                item = request_q.get(timeout=0.5)
            except queue.Empty:
                continue

            req_id, device_id, uri, method, data_str = item
            tag = _short_device_id(device_id)

            full_data = None
            if full_mode and data_str:
                full_data = _fetch_full_response(uri, method, data_str)
                if full_data and "_error" in full_data:
                    safe_print(f"  [{tag}] requests调用失败: {full_data['_error']}", Colors.DIM)

            display_q.put((req_id, device_id, uri, method, data_str, full_data))
            request_q.task_done()

    # ============ 显示 Worker（单线程，保证输出顺序） ============

    def display_worker():
        """从显示队列取结果，格式化输出到终端"""
        while not stop_event.is_set():
            try:
                item = display_q.get(timeout=0.5)
            except queue.Empty:
                continue

            req_id, device_id, uri, method, data_str, full_data = item
            tag = _short_device_id(device_id)

            # 解析请求数据
            data, _ = _parse_request_data([data_str] if data_str else [])

            # 状态追踪（线程安全）
            with state_lock:
                is_new = uri not in seen_uris
                if is_new:
                    seen_uris.add(uri)
                    discovered_apis.append({
                        "uri": uri, "method": method, "data": data_str
                    })
                request_count[0] += 1
                is_known = uri in known_urls

            # 显示
            path = uri.replace(BASE_URL, "")
            prefix = f"[{tag}] "

            safe_print("", Colors.RESET)  # 空行分隔

            if is_error := (full_data and "_error" in full_data):
                safe_print(f"{prefix}!! {method} {path}", Colors.RED, bold=True)
            elif is_new:
                safe_print(f"{prefix}>> {method} {path} [NEW]", Colors.GREEN, bold=True)
            else:
                safe_print(f"{prefix}>> {method} {path}", Colors.BLUE)

            # 请求参数
            if data and data != {"raw": ""}:
                data_display = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)
                safe_print(f"{prefix}   请求: {data_display}", Colors.DIM)

            # 响应体
            if full_data:
                if "_error" in full_data:
                    safe_print(f"{prefix}   响应: (requests调用失败: {full_data['_error']})", Colors.RED)
                else:
                    source_tag = " [requests]" if full_mode else " [logcat]"
                    resp_display = json.dumps(full_data, ensure_ascii=False, indent=2)
                    safe_print(f"{prefix}   响应{source_tag}:\n{resp_display}", Colors.WHITE)
            elif is_error:
                safe_print(f"{prefix}   响应: (异常/无响应)", Colors.RED)
            else:
                safe_print(f"{prefix}   响应: (等待中...)", Colors.DIM)

            # 自动存入记忆库
            if not is_known:
                added = _memory_mgr.add(uri, method, data_str)
                if added:
                    safe_print(f"  [{tag}]  已存入记忆库: {method} {path}", Colors.DIM)

            display_q.task_done()

    # ============ Logcat 读取线程（每设备一个） ============

    def process_line(content, device_id, buf):
        """
        处理一行 logcat 输出，解析DIO请求/响应。
        当请求完整时放入请求队列。
        返回值：是否触发了请求入队（用于计数）
        """
        enqueued = False

        # ---- 新请求开始 → 先把上一个完整的请求入队 ----
        if "*** Request ***" in content:
            if buf["uri"] and buf["method"]:
                req_id = buf["seq"]
                request_q.put((req_id, device_id, buf["uri"], buf["method"], " ".join(buf["data_lines"])))
                enqueued = True
            # 重置缓冲区
            buf["seq"] += 1
            buf["uri"] = None
            buf["method"] = None
            buf["data_lines"] = []
            buf["auth"] = None
            buf["refresh"] = None
            buf["response_lines"] = []
            buf["in_data"] = False
            buf["in_response"] = False
            return enqueued

        # ---- 响应开始 ----
        elif "*** Response ***" in content:
            buf["in_response"] = "headers"
            buf["response_lines"] = []
            return enqueued

        # ---- Dio 异常 ----
        elif "*** DioException ***" in content:
            if buf["uri"] and buf["method"]:
                req_id = buf["seq"]
                request_q.put((req_id, device_id, buf["uri"], buf["method"], " ".join(buf["data_lines"])))
                enqueued = True
            buf["uri"] = None
            buf["in_response"] = False
            return enqueued

        # ---- 响应体 ----
        elif buf["in_response"] == "headers" and "Response Text:" in content:
            buf["in_response"] = "body"
            after_marker = content.split("Response Text:")[-1].strip()
            if after_marker and "[DIO]" not in after_marker:
                buf["response_lines"].append(after_marker)
            return enqueued

        elif buf["in_response"] == "body" and content:
            if "[DIO]" in content:
                after_dio = content.split("[DIO]")[-1].strip()
                if after_dio and not after_dio.startswith("***"):
                    buf["response_lines"].append(after_dio)
            else:
                buf["in_response"] = False
            return enqueued

        # ---- 解析请求头 ----
        elif "uri:" in content and "https://" in content:
            m = re.search(r'uri:\s*(https?://\S+)', content)
            if m:
                buf["uri"] = m.group(1).strip()
                # 提前过滤隐藏接口
                path = buf["uri"].replace(BASE_URL, "")
                if any(h in path for h in hide_list):
                    buf["uri"] = None  # 标记为隐藏，后续不再处理
            return enqueued

        elif "method:" in content:
            m = re.search(r'method:\s*(\w+)', content)
            if m:
                buf["method"] = m.group(1).strip()
            return enqueued

        elif "Authorization:" in content:
            m = re.search(r'Authorization:\s*(\S+)', content)
            if m:
                buf["auth"] = m.group(1).strip()
            return enqueued

        elif "refresh_token:" in content:
            m = re.search(r'refresh_token:\s*(\S+)', content)
            if m:
                buf["refresh"] = m.group(1).strip()
            return enqueued

        # ---- 解析请求体（data） ----
        elif "data:" in content:
            buf["in_data"] = True
            buf["data_lines"] = []
            after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
            if "{" in after_dio and after_dio != "data:":
                buf["data_lines"].append(after_dio.replace("data:", "").strip())
            return enqueued

        elif buf["in_data"]:
            after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
            if "*** " in after_dio or after_dio == "":
                buf["in_data"] = False
            elif after_dio and ("{" in after_dio or after_dio.startswith('"') or ":" in after_dio):
                buf["data_lines"].append(after_dio)
            return enqueued

        return enqueued

    def logcat_reader(device_id):
        """为单个设备启动 logcat 流，实时解析DIO日志"""
        adb_cmd = ["adb", "-s", device_id, "logcat"]
        tag = _short_device_id(device_id)
        proc = None
        buf = {
            "seq": 0,
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

            stdout_reader = io.TextIOWrapper(proc.stdout, encoding='utf-8', errors='replace', line_buffering=True)

            for line in stdout_reader:
                if stop_event.is_set():
                    break
                content = line.strip()
                process_line(content, device_id, buf)

        except Exception as e:
            safe_print(f"  [{tag}] logcat错误: {e}", Colors.RED)
        finally:
            # 最后一个请求丢入队列
            if buf["uri"] and buf["method"]:
                request_q.put((buf["seq"], device_id, buf["uri"], buf["method"], " ".join(buf["data_lines"])))
            if proc:
                proc.terminate()

    # ============ 启动线程 ============

    # 1. 每个设备一个 logcat 读取线程
    logcat_threads = []
    for device_id in devices:
        t = threading.Thread(target=logcat_reader, args=(device_id,), daemon=True)
        t.start()
        logcat_threads.append(t)

    # 2. HTTP worker 线程池（--full 模式，并行获取响应）
    worker_threads = []
    if full_mode:
        http_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="http-worker")
        for _ in range(4):
            ft = http_pool.submit(http_worker)
            worker_threads.append(ft)

    # 3. 显示 worker 单线程（保证输出不乱序）
    display_thread = threading.Thread(target=display_worker, daemon=True)
    display_thread.start()

    # ============ 主线程等待 Ctrl+C ============

    try:
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

        # 等待队列处理完
        try:
            request_q.join(timeout=5)
        except Exception:
            pass

        # 关闭 HTTP 线程池
        if full_mode:
            http_pool.shutdown(wait=False)

        # 等待显示队列处理完
        try:
            display_q.join(timeout=5)
        except Exception:
            pass

        # 保存记忆库
        _memory_mgr.shutdown()

        new_count = len(seen_uris) - len(known_urls)
        cprint(f"\n已停止，共捕获 {request_count[0]} 个请求，发现 {new_count} 个新接口", Colors.DIM)

        if discovered_apis:
            cprint("\n发现的接口列表:", Colors.YELLOW, bold=True)
            for api in discovered_apis:
                cprint(f"  {api['method']} {api['uri'].replace(BASE_URL, '')}", Colors.WHITE)
            cprint(f"\n提示: 将新接口添加到 api_tool.py 的 presets 中即可用 call 命令调用", Colors.DIM)


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
    device = None
    devices = None

    if args.command == "auto":
        if args.device:
            devices = args.device
            for d in devices:
                cprint(f"指定设备: {d}", Colors.CYAN)
        else:
            all_devices = []
            try:
                result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                for line in result.stdout.strip().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        all_devices.append(parts[0])
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            if all_devices:
                devices = all_devices
            else:
                devices = [ADB_DEVICE] if ADB_DEVICE else None

        args._devices = devices
    else:
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
