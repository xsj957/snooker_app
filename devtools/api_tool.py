#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 抓包调试工具 v3.1
功能：实时抓包 + 智能阈值 + Chrome DevTools 风格 HTML 界面
      小响应直接用 logcat 数据，大响应才走 Python requests 绕过截断

用法：python devtools/api_tool.py <command> [options]

命令：
  log     - 实时查看 App 网络日志（类似 tail -f | grep）
  extract - 从日志文件提取所有 API 接口信息
  call    - 调用指定接口并显示完整响应
  auto    - 实时监控 + 自动发现新接口 + DevTools 风格 HTML 界面
  list    - 列出所有已发现的接口

全局参数：
  -s, --device  指定 ADB 设备 ID（多设备时必须指定）
                设备 ID 可通过 adb devices 查看
                示例：python devtools/api_tool.py auto -s 设备ID

auto 专用参数：
  --full        智能获取完整响应（小响应直接用 logcat，大响应才走 Python requests 绕过截断）
                示例：python devtools/api_tool.py auto --full
  --html        启动 HTML DevTools 界面（浏览器访问 http://localhost:8765）
                示例：python devtools/api_tool.py auto --full --html
  --port        HTML 服务端口（默认 8765）
"""

import sys
import os

# 兼容直接运行: python devtools/api_tool.py
# 使 devtools/ 可被当作包导入，同时 server 模块可被找到
_devtools_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_devtools_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
import subprocess
import re
import json
import time
import io
import requests
import threading
import queue
from collections import OrderedDict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ============== 从 devtools.server 导入后端 ==============

from devtools import server as _server
from devtools.server import (
    BASE_URL, HEADERS, USER_ID,
    Colors, cprint, safe_print,
    _memory_mgr, _parse_request_data, _fetch_full_response,
    _decode_jwt_payload, _auto_auth, _auto_auth_lock,
    log_buffer, configure,
    start_html_server,
    format_time, format_size, short_device_id,
    next_log_id,
)

# ============== ADB 设备检测 ==============


def get_adb_device():
    """动态获取已连接的 ADB 设备序列号"""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


ADB_DEVICE = get_adb_device()


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

    apis = OrderedDict()
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        if "*** Request ***" in line:
            uri = method = None
            data_lines = []

            j = i + 1
            while j < min(i + 30, len(lines)):
                l = lines[j]
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

    cprint(f"\n共发现 {len(apis)} 个接口:\n", Colors.GREEN, bold=True)

    for idx, (key, api) in enumerate(apis.items(), 1):
        cprint(f"  {idx}. {key}", Colors.BOLD)
        cprint(f"     URL: {api['url']}", Colors.DIM)
        if api["data"]:
            data_str = json.dumps(api["data"], ensure_ascii=False, indent=6)
            cprint(f"     Data: {data_str}", Colors.DIM)
        print()

    if args.save:
        output_file = args.save
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(apis, f, ensure_ascii=False, indent=2)
        cprint(f"已保存到: {output_file}", Colors.GREEN)


# ============== 调用指定接口 ==============

def cmd_call(args):
    """调用指定接口并显示完整响应"""

    presets = {
        "user": {
            "name": "获取用户信息",
            "method": "POST",
            "url": f"{BASE_URL}/mp/user/info",
            "data": {"userId": _server.USER_ID}
        },
        "box": {
            "name": "获取盒子状态",
            "method": "POST",
            "url": f"{BASE_URL}/mobile/getUserBoxStatus",
            "data": {"userId": _server.USER_ID}
        },
        "version": {
            "name": "检查版本",
            "method": "POST",
            "url": f"{BASE_URL}/mp/app/version/check",
            "data": {"platform": 2, "currentVersion": "1.0.0", "userId": _server.USER_ID}
        },
        "coupon": {
            "name": "检查视频券",
            "method": "POST",
            "url": f"{BASE_URL}/mp/coupon/checkEligibility",
            "data": {"userId": _server.USER_ID}
        },
        "matches": {
            "name": "对手列表和视频",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/opponentListWithVideos",
            "data": {"userId": _server.USER_ID}
        },
        "track": {
            "name": "埋点上报",
            "method": "POST",
            "url": f"{BASE_URL}/mp/event/track",
            "data": {"modelType": 1, "eventType": 5, "attrName": "me", "attrValue": None, "clientType": 1, "userId": _server.USER_ID}
        },
    }

    if args.name in presets:
        api = presets[args.name]
    elif args.url:
        api = {
            "name": args.name or args.url,
            "method": "POST",
            "url": args.url,
            "data": json.loads(args.data) if args.data else {"userId": _server.USER_ID}
        }
    else:
        memory = _memory_mgr.get()
        if args.name in memory:
            api = memory[args.name]
            api["name"] = args.name
        else:
            cprint(f"未知接口: {args.name}", Colors.RED)
            cprint(f"\n内置快捷名称: {', '.join(presets.keys())}", Colors.YELLOW)
            return

    cprint(f"\n调用: {api['name']}", Colors.CYAN, bold=True)
    cprint(f"URL: {api['url']}", Colors.BLUE)
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

        try:
            result = resp.json()
            formatted = json.dumps(result, ensure_ascii=False, indent=2)
            cprint(f"\n{formatted}", Colors.WHITE)
        except (json.JSONDecodeError, ValueError):
            cprint(f"\n{resp.text}", Colors.WHITE)

    except requests.exceptions.RequestException as e:
        cprint(f"请求失败: {e}", Colors.RED)


# ============== 列出所有接口 ==============

def cmd_list(_args):
    """列出所有已知接口"""
    presets = {
        "user": "POST /mp/user/info - 获取用户信息",
        "box": "POST /mobile/getUserBoxStatus - 获取盒子状态",
        "version": "POST /mp/app/version/check - 检查版本",
        "coupon": "POST /mp/coupon/checkEligibility - 检查视频券",
        "matches": "POST /mp/record/opponentListWithVideos - 对手列表和视频",
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

    cprint(f"\n调用示例: python devtools/api_tool.py call user", Colors.DIM)


# ============== 自动模式 v3.0（DevTools 风格） ==============

def cmd_auto(args):
    """实时监控 + DevTools 风格 HTML 界面"""
    # 智能阈值：logcat 响应字符数低于此值时直接使用，超过则走 Python requests 获取完整响应
    # Android logcat 单行限制 ~4096 字节，接近此长度的行可能被截断
    RESPONSE_SIZE_THRESHOLD = 3500

    devices = getattr(args, '_devices', None)
    if not devices:
        cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
        return

    full_mode = getattr(args, 'full', False)
    html_mode = getattr(args, 'html', False)
    html_port = getattr(args, 'port', 8765)
    hide_list = getattr(args, 'hide', []) or []
    restart_app = getattr(args, 'restart', False)
    pkg_override = getattr(args, 'pkg', None)

    if len(devices) > 1:
        cprint(f"自动监控模式 v3.0 | {len(devices)} 台设备并行", Colors.CYAN, bold=True)
        for d in devices:
            tag = f"[{short_device_id(d)}]"
            cprint(f"  {tag} {d}", Colors.DIM)
    else:
        cprint(f"自动监控模式 v3.0 | 设备: {devices[0]}", Colors.CYAN, bold=True)

    if full_mode:
        cprint("模式: 智能阈值（小响应直接用 logcat，大响应走 Python）", Colors.CYAN)
    else:
        cprint("模式: logcat 监听（小响应直接显示）", Colors.CYAN)

    # html_server 由重连循环管理
    html_server = None

    if hide_list:
        cprint(f"已隐藏接口: {', '.join(hide_list)}", Colors.DIM)
    cprint("Ctrl+C 停止", Colors.DIM)
    cprint("=" * 60)

    # 启动前重置日志缓冲区，确保不残留上次运行的数据
    log_buffer.reset()

    # 初始化已知接口
    builtin_paths = {
        "/mp/user/info", "/mp/user/myClubs", "/mp/user/saveDefaultClub",
        "/mp/user/rating", "/mp/user/breakScoreList",
        "/mp/oauth/wechatLogin", "/mobile/getUserBoxStatus",
        "/mobile/loginBoxAfterScanningQrCode",
        "/mp/app/version/check", "/mp/coupon/checkEligibility",
        "/mp/coupon/trialList", "/mp/coupon/queryCouponList",
        "/video/videoClient/getVideoStatistics",
        "/video/videoClient/myVideos/processingV2",
        "/video/videoClient/myVideos/readyV2",
        "/video/videoClient/myVideos/failedV2",
        "/video/videoClient/updateClientInfo",
        "/video/videoClient/updateStatus",
        "/mp/record/opponentListWithVideos",
        "/mp/record/opponentStatistics", "/mp/record/competitionListWithVideos",
        "/mp/record/competitionStatistics",
        "/mp/record/inningList", "/mp/record/inningStatistics",
        "/mp/record/markVideoViewed", "/mp/record/deviceOnlineInfo",
        "/mp/record/barchart", "/mp/record/statics",
        "/video/videoinfo/competitionVideos", "/video/videoinfo/buyitUseComboV3",
        "/mp/rank/clubList", "/mp/rank/userBreakRank",
        "/mp/rank/ratingList", "/mp/rank/breakList", "/mp/rank/winRateList",
        "/mp/event/track",
    }
    known_urls = {f"{BASE_URL}{p}" for p in builtin_paths}
    known_urls.update(_memory_mgr.known_urls())

    state_lock = threading.Lock()
    seen_uris = set(known_urls)
    discovered_apis = []
    request_count = [0]

    # request_q / display_q / stop_event 在重连循环内每次重建
    # 防止旧 worker 线程在新会话中复活（stop_event.clear() 不会唤醒它们）

    def http_worker():
        """异步 HTTP Worker：获取完整响应 + 状态码/headers/size/timing"""
        while not stop_event.is_set():
            try:
                item = request_q.get(timeout=0.5)
            except queue.Empty:
                continue

            req_id, device_id, uri, method, data_str, req_headers = item

            full_resp = _fetch_full_response(uri, method, data_str)

            display_q.put((
                req_id, device_id, uri, method, data_str,
                full_resp.get('status', 0),
                full_resp.get('headers', {}),
                full_resp.get('body'),
                full_resp.get('size', 0),
                full_resp.get('time_ms', 0),
                full_resp.get('error'),
                req_headers,
                full_resp.get('timing', {}),
            ))
            request_q.task_done()

    def display_worker():
        """显示 Worker：处理 HTTP worker 返回的大响应（小响应已由 _complete_request 直接处理）"""
        while not stop_event.is_set():
            try:
                item = display_q.get(timeout=0.5)
            except queue.Empty:
                continue

            (req_id, device_id, uri, method, data_str,
             status_code, resp_headers, resp_body, resp_size, time_ms, error, req_headers,
             timing_info) = item

            tag = short_device_id(device_id)
            data, _ = _parse_request_data([data_str] if data_str else [])

            with state_lock:
                is_new = uri not in seen_uris
                if is_new:
                    seen_uris.add(uri)
                    # 过滤 CDN 视频原片，不进入已发现列表
                    if not re.search(r'\.mp4(\?|$)', uri):
                        discovered_apis.append({"uri": uri, "method": method, "data": data_str})
                request_count[0] += 1
                is_known = uri in known_urls

            path = uri.replace(BASE_URL, "")
            prefix = f"[{tag}] "
            is_error = error is not None

            # HTTP worker 获取的完整响应 — 终端输出
            if is_error:
                safe_print(f"{prefix}!! {method} {path} [{status_code}]", Colors.RED, bold=True)
            elif is_new:
                safe_print(f"{prefix}>> {method} {path} [{status_code}] [NEW] 🔍http", Colors.GREEN, bold=True)
            else:
                safe_print(f"{prefix}>> {method} {path} [{status_code}] 🔍http", Colors.BLUE)

            if data and data != {"raw": ""}:
                data_display = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)
                safe_print(f"{prefix}   请求: {data_display}", Colors.DIM)

            # 格式化响应 body（提前处理，HTML 模式复用）
            response_body = resp_body
            response_raw = None
            if resp_body is not None:
                if isinstance(resp_body, (dict, list)):
                    response_raw = json.dumps(resp_body, ensure_ascii=False, separators=(',', ':'))
                else:
                    response_raw = str(resp_body)

            if resp_body is not None and not is_error:
                resp_display = json.dumps(resp_body, ensure_ascii=False, indent=2) if isinstance(resp_body, (dict, list)) else str(resp_body)
                safe_print(f"{prefix}   响应 [{status_code}] ({format_time(time_ms)}, {format_size(resp_size)}):\n{resp_display}", Colors.WHITE)
            elif is_error:
                safe_print(f"{prefix}   响应: (请求异常: {error})", Colors.RED)
            else:
                safe_print(f"{prefix}   响应: (空)", Colors.DIM)

            # 存入记忆库
            if not is_known:
                added = _memory_mgr.add(uri, method, data_str)
                if added:
                    safe_print(f"  [{tag}]  已存入记忆库: {method} {path}", Colors.DIM)

            # HTML 模式：存入日志缓冲区
            if html_mode:
                log_entry = {
                    'id': next_log_id(),  # 全局唯一递增 ID，避免多设备 per-buffer seq 冲突
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'device': tag,
                    'method': method,
                    'path': path,
                    'full_url': uri,
                    'status': status_code,
                    'size': resp_size,
                    'time_ms': time_ms,
                    'timing': timing_info,
                    'is_new': is_new,
                    'is_error': is_error,
                    'request_data': data if data and data != {"raw": ""} else None,
                    'request_headers': req_headers,
                    'response_headers': resp_headers or {},
                    'response_body': response_body,
                    'response_raw': response_raw,
                    'error': error,
                    'source': 'http',
                }
                log_buffer.add(log_entry)

            display_q.task_done()

    def _try_auto_auth(tag=""):
        """从 logcat 捕获的认证信息自动配置（只需成功一次）"""
        with _auto_auth_lock:
            if _auto_auth['detected']:
                return
            # 用户手动指定了认证信息，跳过自动检测
            if getattr(args, 'user', None) or getattr(args, 'token', None):
                return
            if _auto_auth['token'] and _auto_auth['refresh_token']:
                _auto_auth['detected'] = True
                # 解码 JWT 获取 user_id
                if not _auto_auth['user_id']:
                    payload = _decode_jwt_payload(_auto_auth['token'])
                    _auto_auth['user_id'] = payload.get('userId')
                token = _auto_auth['token']
                refresh_token = _auto_auth['refresh_token']
                user_id = _auto_auth['user_id']
        # 在锁外调用 configure，避免持锁过久
        if _auto_auth.get('detected'):
            configure(user_id=user_id, token=token, refresh_token=refresh_token)
            uid = user_id or '(未知)'
            safe_print(f"  [{tag}]  自动检测到用户身份: {uid}", Colors.GREEN)

    def _complete_request(buf, device_id, reason="next_request"):
        """
        完成一个请求 — 智能判断使用 logcat 响应还是 Python requests
        小响应（< RESPONSE_SIZE_THRESHOLD 字符）直接用 logcat 捕获的响应
        大响应或疑似截断的响应走 Python HTTP worker 获取完整数据
        非 --full 模式始终使用 logcat 响应（不走 HTTP worker）
        """
        if not buf["uri"] or not buf["method"]:
            return

        tag = short_device_id(device_id)
        data_str = " ".join(buf["data_lines"])
        req_headers = dict(buf["req_headers"]) if buf["req_headers"] else {}
        response_raw = "".join(buf["response_lines"])

        # 判断是否直接使用 logcat 响应
        if not full_mode:
            # 非 --full 模式：始终使用 logcat 响应
            use_logcat = True
        elif len(response_raw) < RESPONSE_SIZE_THRESHOLD:
            # 小响应：直接使用 logcat 捕获的数据
            use_logcat = True
        else:
            # 大响应：走 Python HTTP 重新获取完整数据
            use_logcat = False

        if use_logcat:
            # === 直接使用 logcat 捕获的响应 ===
            body = None
            if response_raw:
                try:
                    body = json.loads(response_raw)
                except (json.JSONDecodeError, ValueError):
                    body = response_raw

            # 从响应 body 中推断 status code
            status = 200
            if isinstance(body, dict) and 'code' in body:
                try:
                    code = int(body['code'])
                    if code in (0, 200):
                        status = 200
                    else:
                        status = code
                except (ValueError, TypeError):
                    pass

            size = len(response_raw.encode('utf-8')) if response_raw else 0
            req_id = next_log_id()  # 全局唯一 ID，避免多设备 buf['seq'] 冲突

            # 终端输出
            path = buf["uri"].replace(BASE_URL, "")
            data_parsed, _ = _parse_request_data([data_str] if data_str else [])

            with state_lock:
                is_new = buf["uri"] not in seen_uris
                if is_new:
                    seen_uris.add(buf["uri"])
                    if not re.search(r'\.mp4(\?|$)', buf["uri"]):
                        discovered_apis.append({"uri": buf["uri"], "method": buf["method"], "data": data_str})
                request_count[0] += 1
                is_known = buf["uri"] in known_urls

            if reason == "exception":
                safe_print(f"\n[{tag}] !! {buf['method']} {path} [ERR]", Colors.RED, bold=True)
            elif is_new:
                safe_print(f"\n[{tag}] >> {buf['method']} {path} [{status}] [NEW] ⚡logcat", Colors.GREEN, bold=True)
            else:
                safe_print(f"\n[{tag}] >> {buf['method']} {path} [{status}] ⚡logcat", Colors.BLUE)

            if data_parsed and data_parsed != {"raw": ""}:
                data_display = json.dumps(data_parsed, ensure_ascii=False, indent=2) if isinstance(data_parsed, dict) else str(data_parsed)
                safe_print(f"[{tag}]    请求: {data_display}", Colors.DIM)

            if body is not None:
                resp_display = json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, (dict, list)) else str(body)
                safe_print(f"[{tag}]    响应 [{status}] ({format_size(size)}):\n{resp_display}", Colors.WHITE)

            # 存入记忆库
            if not is_known:
                added = _memory_mgr.add(buf["uri"], buf["method"], data_str)
                if added:
                    safe_print(f"  [{tag}]   已存入记忆库: {buf['method']} {path}", Colors.DIM)

            # HTML 模式：存入日志缓冲区
            if html_mode:
                response_raw_json = None
                if body is not None:
                    if isinstance(body, (dict, list)):
                        response_raw_json = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
                    else:
                        response_raw_json = str(body)

                # DioException 时标记为错误
                is_exception = (reason == "exception")
                log_entry = {
                    'id': req_id,
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'device': tag,
                    'method': buf["method"],
                    'path': path,
                    'full_url': buf["uri"],
                    'status': 0 if is_exception else status,
                    'size': size,
                    'time_ms': 0,
                    'timing': {},
                    'is_new': is_new,
                    'is_error': is_exception,
                    'request_data': data_parsed if data_parsed and data_parsed != {"raw": ""} else None,
                    'request_headers': req_headers,
                    'response_headers': dict(buf["resp_headers"]) if buf["resp_headers"] else {},
                    'response_body': body,
                    'response_raw': response_raw_json,
                    'error': 'DioException' if is_exception else None,
                    'source': 'logcat',
                }
                log_buffer.add(log_entry)
        else:
            # === 走 Python HTTP worker 获取完整响应 ===
            safe_print(f"\n[{tag}] ⟳ {buf['method']} {buf['uri'].replace(BASE_URL, '')} → Python 获取完整响应...", Colors.YELLOW)
            request_q.put((buf["seq"], device_id, buf["uri"], buf["method"],
                           data_str, req_headers))

    def process_line(content, device_id, buf):
        """处理 logcat 行 — 解析 Dio 日志协议"""
        tag = short_device_id(device_id)

        if "*** Request ***" in content:
            _complete_request(buf, device_id, reason="next_request")
            buf["seq"] += 1
            buf["uri"] = None
            buf["method"] = None
            buf["data_lines"] = []
            buf["req_headers"] = {}
            buf["response_lines"] = []
            buf["resp_headers"] = {}
            buf["in_data"] = False
            buf["in_response"] = False
            # 重置当前请求的认证捕获缓冲
            buf["captured_auth"] = False
            buf["captured_refresh"] = False
            return

        elif "*** Response ***" in content:
            buf["in_response"] = "headers"
            buf["response_lines"] = []
            buf["resp_headers"] = {}
            return

        elif "*** DioException ***" in content:
            _complete_request(buf, device_id, reason="exception")
            # 完整重置 buf，防止脏数据泄漏到下一个请求
            buf["uri"] = None
            buf["method"] = None
            buf["data_lines"] = []
            buf["req_headers"] = {}
            buf["response_lines"] = []
            buf["resp_headers"] = {}
            buf["in_data"] = False
            buf["in_response"] = False
            buf["captured_auth"] = False
            buf["captured_refresh"] = False
            return

        elif buf["in_response"] == "headers":
            if "Response Text:" in content:
                buf["in_response"] = "body"
                after_marker = content.split("Response Text:")[-1].strip()
                if after_marker and "[DIO]" not in after_marker:
                    buf["response_lines"].append(after_marker)
            elif content.strip():
                m = re.match(r'^([\w\-]+)\s*:\s*(.+)$', content)
                if m:
                    buf["resp_headers"][m.group(1).strip()] = m.group(2).strip()
            return

        elif buf["in_response"] == "body":
            if content:
                if "[DIO]" in content:
                    after_dio = content.split("[DIO]")[-1].strip()
                    if after_dio and not after_dio.startswith("***"):
                        buf["response_lines"].append(after_dio)
                else:
                    buf["in_response"] = False
            return

        elif "uri:" in content and "https://" in content:
            m = re.search(r'uri:\s*(https?://\S+)', content)
            if m:
                buf["uri"] = m.group(1).strip()
                # 过滤 CDN 视频原片（.mp4），不抓不存
                if re.search(r'\.mp4(\?|$)', buf["uri"]):
                    buf["uri"] = None
                    return
                path = buf["uri"].replace(BASE_URL, "")
                if any(h in path for h in hide_list):
                    buf["uri"] = None
            return

        elif "method:" in content:
            m = re.search(r'method:\s*(\w+)', content)
            if m:
                buf["method"] = m.group(1).strip()
            return

        elif "Authorization:" in content and buf.get("req_headers") is not None:
            m = re.search(r'Authorization:\s*(\S+)', content)
            if m:
                token = m.group(1).strip()
                buf["req_headers"]["Authorization"] = token
                # 自动认证：提取 JWT token
                should_auth = False
                with _auto_auth_lock:
                    if not _auto_auth['detected'] and not buf.get("captured_auth"):
                        _auto_auth['token'] = token
                        buf["captured_auth"] = True
                        payload = _decode_jwt_payload(token)
                        if payload.get('userId'):
                            _auto_auth['user_id'] = payload['userId']
                        should_auth = True
                if should_auth:
                    _try_auto_auth(tag)
            return

        elif "refresh_token:" in content and buf.get("req_headers") is not None:
            m = re.search(r'refresh_token:\s*(\S+)', content)
            if m:
                rt = m.group(1).strip()
                buf["req_headers"]["refresh_token"] = rt
                # 自动认证：提取 refresh_token
                should_auth = False
                with _auto_auth_lock:
                    if not _auto_auth['detected'] and not buf.get("captured_refresh"):
                        _auto_auth['refresh_token'] = rt
                        buf["captured_refresh"] = True
                        should_auth = True
                if should_auth:
                    _try_auto_auth(tag)
            return

        elif "data:" in content:
            buf["in_data"] = True
            buf["data_lines"] = []
            after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
            if "{" in after_dio and after_dio != "data:":
                buf["data_lines"].append(after_dio.replace("data:", "").strip())
            return

        elif buf["in_data"]:
            after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
            if "*** " in after_dio or after_dio == "":
                buf["in_data"] = False
            elif after_dio and ("{" in after_dio or after_dio.startswith('"') or ":" in after_dio):
                buf["data_lines"].append(after_dio)
                # 自动认证：从请求体中提取 userId
                if not _auto_auth['detected'] and not _auto_auth['user_id']:
                    data_str = " ".join(buf["data_lines"])
                    try:
                        data = json.loads(data_str)
                        if isinstance(data, dict) and 'userId' in data and data['userId']:
                            _auto_auth['user_id'] = data['userId']
                            _try_auto_auth(tag)
                    except (json.JSONDecodeError, ValueError):
                        pass
            return

    def logcat_reader(device_id):
        """logcat 读取线程"""
        adb_cmd = ["adb", "-s", device_id, "logcat"]
        tag = short_device_id(device_id)
        proc = None

        # 启动流式读取前，先排空设备端 logcat 环形缓冲区中的残留历史条目
        # adb logcat -c 清空后，USB 管道可能仍残留旧数据；-d 模式一次性读走这些残留
        try:
            for _ in range(3):
                drain = subprocess.run(
                    ["adb", "-s", device_id, "logcat", "-d", "-v", "brief"],
                    capture_output=True, text=True, timeout=3
                )
                if not drain.stdout or not drain.stdout.strip():
                    break
        except Exception as e:
            safe_print(f"  [{tag}] logcat缓冲区排空失败(不影响使用): {e}", Colors.DIM)

        buf = {
            "seq": 0,
            "uri": None, "method": None,
            "data_lines": [], "req_headers": {},
            "response_lines": [], "resp_headers": {},
            "in_data": False, "in_response": False,
            "captured_auth": False, "captured_refresh": False,
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
            _complete_request(buf, device_id, reason="flush")
            if proc:
                proc.terminate()

    # 检测 App 包名（--pkg 指定优先，否则自动扫描已安装的斯诺克大师包）
    _pkg_cache = {}

    def _detect_pkg(device_id):
        if pkg_override:
            return pkg_override
        if device_id in _pkg_cache:
            return _pkg_cache[device_id]
        for pkg in ("com.supervisions.snookermastercn", "com.supervisions.snookermaster"):
            try:
                r = subprocess.run(
                    ["adb", "-s", device_id, "shell", "pm", "path", pkg],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0 and "package:" in r.stdout:
                    _pkg_cache[device_id] = pkg
                    return pkg
            except Exception:
                pass
        # 缓存 None，避免每次重连重复探测
        _pkg_cache[device_id] = None
        return None

    # ============== USB 断开检测 + 重连循环 ==============
    disconnect_detected = [False]
    user_abort = [False]
    total_requests = [0]
    all_discovered = []
    session_id = [0]  # 每次循环迭代递增，旧 watchdog 据此自动退出

    def _device_watchdog(my_session):
        """监控所有 ADB 设备连接状态，任一设备断开时触发清理"""
        check_interval = 3
        consecutive_failures = {}  # per-device failure count
        for d in devices:
            consecutive_failures[d] = 0
        while not stop_event.is_set():
            time.sleep(check_interval)
            if stop_event.is_set() or session_id[0] != my_session:
                break
            for dev in devices:
                try:
                    result = subprocess.run(
                        ["adb", "-s", dev, "get-state"],
                        capture_output=True, text=True, timeout=3
                    )
                    if result.returncode == 0 and "device" in result.stdout:
                        consecutive_failures[dev] = 0
                    else:
                        consecutive_failures[dev] = consecutive_failures.get(dev, 0) + 1
                        if consecutive_failures[dev] >= 2:
                            if not disconnect_detected[0] and session_id[0] == my_session:
                                disconnect_detected[0] = True
                                tag = short_device_id(dev)
                                safe_print(f"\n  [{tag}] ⚠ 设备连接丢失，正在清理...", Colors.YELLOW, bold=True)
                                stop_event.set()
                            return
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    consecutive_failures[dev] = consecutive_failures.get(dev, 0) + 1
                    if consecutive_failures[dev] >= 2:
                        if not disconnect_detected[0] and session_id[0] == my_session:
                            disconnect_detected[0] = True
                            tag = short_device_id(dev)
                            safe_print(f"\n  [{tag}] ⚠ 设备连接丢失，正在清理...", Colors.YELLOW, bold=True)
                            stop_event.set()
                        return

    # ============== 重连循环 ==============
    while True:
        # 递增 session ID，使上一轮的 watchdog 自动退出
        session_id[0] += 1
        current_session = session_id[0]

        # 每次重连创建全新的队列和事件（旧 worker 持有旧引用，无法复活）
        request_q = queue.Queue()
        display_q = queue.Queue()
        stop_event = threading.Event()
        disconnect_detected[0] = False

        # 重置自动认证状态，使新会话重新从 logcat 捕获 token
        with _auto_auth_lock:
            _auto_auth['detected'] = False
            _auto_auth['token'] = None
            _auto_auth['refresh_token'] = None
            _auto_auth['user_id'] = None

        # 清空包名缓存，允许重新检测（用户可能在断连期间安装了 App）
        _pkg_cache.clear()

        # 清空上一次会话的 HTML 缓冲
        log_buffer.clear()

        # 重置会话计数器
        seen_uris.clear()
        seen_uris.update(known_urls)
        discovered_apis.clear()
        request_count[0] = 0

        # 重启 HTML 服务（释放旧端口，重新绑定）
        if html_mode:
            if html_server:
                try:
                    html_server.shutdown()
                except Exception:
                    pass
                time.sleep(0.5)
            try:
                html_server, actual_port = start_html_server(html_port)
                cprint(f"  DevTools 界面: http://localhost:{actual_port}", Colors.GREEN, bold=True)
            except Exception as e:
                cprint(f"  HTML 服务启动失败: {e}", Colors.RED)

        # 重启 App / 清空 logcat
        if restart_app:
            for device_id in devices:
                tag = short_device_id(device_id)
                pkg = _detect_pkg(device_id)
                if not pkg:
                    continue
                try:
                    r = subprocess.run(
                        ["adb", "-s", device_id, "shell", "pm", "dump", pkg],
                        capture_output=True, text=True, timeout=10,
                    )
                    activity = None
                    for line in r.stdout.splitlines():
                        if "MAIN" in line and "LAUNCHER" in line:
                            m = re.search(r'(\S+\.MainActivity|\S+\.SplashActivity|\S+\/\S+Activity)', line)
                            if m:
                                activity = m.group(1)
                                break
                    if not activity:
                        activity = f"{pkg}/.MainActivity"
                    subprocess.run(
                        ["adb", "-s", device_id, "shell", "am", "force-stop", pkg],
                        capture_output=True, timeout=5,
                    )
                    subprocess.run(
                        ["adb", "-s", device_id, "logcat", "-c"],
                        capture_output=True, timeout=5,
                    )
                    subprocess.run(
                        ["adb", "-s", device_id, "shell", "am", "start", "-n", activity],
                        capture_output=True, timeout=5,
                    )
                    safe_print(f"  [{tag}] 已重启 App，等待 3 秒...", Colors.CYAN)
                    time.sleep(3)
                except Exception:
                    pass
        else:
            for device_id in devices:
                tag = short_device_id(device_id)
                try:
                    subprocess.run(["adb", "-s", device_id, "logcat", "-c"],
                                   capture_output=True, timeout=5)
                    safe_print(f"  [{tag}] 已清空 logcat 缓冲区", Colors.DIM)
                except Exception:
                    pass

        # 重新启动 logcat 线程
        logcat_threads = []
        for device_id in devices:
            t = threading.Thread(target=logcat_reader, args=(device_id,), daemon=True)
            t.start()
            logcat_threads.append(t)

        # 重新启动 HTTP worker
        worker_threads = []
        http_pool = None
        if full_mode:
            http_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="http-worker")
            for _ in range(4):
                ft = http_pool.submit(http_worker)
                worker_threads.append(ft)

        # 重新启动 display worker
        display_thread = threading.Thread(target=display_worker, daemon=True)
        display_thread.start()

        # 重新启动 watchdog
        watchdog = threading.Thread(target=_device_watchdog, args=(current_session,), daemon=True)
        watchdog.start()

        safe_print("=" * 60, Colors.DIM)

        try:
            while True:
                time.sleep(0.5)
                if stop_event.is_set():
                    break
                alive = any(t.is_alive() for t in logcat_threads)
                if not alive:
                    cprint("\n所有设备 logcat 流已断开", Colors.DIM)
                    break
        except KeyboardInterrupt:
            user_abort[0] = True
            stop_event.set()

        # 本次会话清理 — 排空队列（Queue.join 无 timeout 参数，改用轮询）
        for q in (request_q, display_q):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if q.unfinished_tasks == 0:
                    break
                time.sleep(0.1)
        if http_pool:
            http_pool.shutdown(wait=False)
        # 清空队列残留，避免下一轮 worker 处理旧请求
        for q in (request_q, display_q):
            while True:
                try:
                    q.get_nowait()
                    q.task_done()
                except Exception:
                    break
        _memory_mgr.flush()

        total_requests[0] += request_count[0]
        all_discovered.extend(discovered_apis)

        if disconnect_detected[0]:
            new_count = len(seen_uris) - len(known_urls)
            cprint(f"本次捕获 {request_count[0]} 个请求，发现 {new_count} 个新接口", Colors.DIM)
            cprint("等待设备重新连接...（Ctrl+C 退出）", Colors.YELLOW)
            # 等待设备重新上线
            while True:
                try:
                    if user_abort[0]:
                        break
                    result = subprocess.run(
                        ["adb", "-s", devices[0], "get-state"],
                        capture_output=True, text=True, timeout=3
                    )
                    if result.returncode == 0 and "device" in result.stdout:
                        cprint("✓ 设备已重新连接，启动新会话...\n", Colors.GREEN, bold=True)
                        time.sleep(1)
                        break
                    time.sleep(3)
                except KeyboardInterrupt:
                    user_abort[0] = True
                    break
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    time.sleep(3)
            if user_abort[0]:
                break
        else:
            break

    # 关闭记忆库定时器，防止 Timer 线程泄漏
    _memory_mgr.shutdown()

    # ============== 最终总结 ==============
    cprint(f"\n已停止，共捕获 {total_requests[0]} 个请求", Colors.DIM)
    if all_discovered:
        cprint("\n发现的接口列表:", Colors.YELLOW, bold=True)
        seen_set = set()
        for api in all_discovered:
            key = f"{api['method']} {api['uri']}"
            if key not in seen_set:
                seen_set.add(key)
                cprint(f"  {api['method']} {api['uri'].replace(BASE_URL, '')}", Colors.WHITE)


# ============== CLI ==============

def main():
    parser = argparse.ArgumentParser(
        description="斯诺克大师 App API 抓包调试工具 v3.0 — DevTools 风格",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python devtools/api_tool.py log                                    # 实时查看日志
  python devtools/api_tool.py extract app_log.txt                    # 从日志文件提取接口
  python devtools/api_tool.py call user                              # 调用用户信息接口
  python devtools/api_tool.py auto --full --html                     # 实时监控 + DevTools 界面（推荐）
  python devtools/api_tool.py --user <ID> --token <JWT> call user    # 指定用户身份调用接口
  python devtools/api_tool.py list                                   # 列出所有已知接口
        """
    )

    # 全局认证参数（所有子命令共享）
    parser.add_argument("--user", help="指定 user_id（覆盖默认值）")
    parser.add_argument("--token", help="指定 Authorization JWT（覆盖默认值）")
    parser.add_argument("--refresh-token", dest="refresh_token", help="指定 refresh_token（覆盖默认值）")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    log_parser = subparsers.add_parser("log", help="实时查看 App 网络日志")
    log_parser.add_argument("-s", "--device", help="指定 ADB 设备 ID")
    log_parser.add_argument("-p", "--pattern", help="过滤关键词 (默认: DIO)")

    ext_parser = subparsers.add_parser("extract", help="从日志文件提取接口")
    ext_parser.add_argument("file", help="日志文件路径")
    ext_parser.add_argument("-s", "--save", help="保存为 JSON 文件")

    call_parser = subparsers.add_parser("call", help="调用指定接口")
    call_parser.add_argument("name", nargs="?", help="接口快捷名称")
    call_parser.add_argument("-u", "--url", help="自定义接口 URL")
    call_parser.add_argument("-d", "--data", help="自定义请求数据 (JSON)")

    auto_parser = subparsers.add_parser("auto", help="实时监控 + DevTools 风格 HTML 界面")
    auto_parser.add_argument("-s", "--device", nargs="+", default=None, help="指定 ADB 设备 ID")
    auto_parser.add_argument("--hide", nargs="*", default=[
        "/mobile/getUserBoxStatus",
        "/mp/user/info",
        "/mp/rank/clubList",
        "/mp/rank/userBreakRank",
        "/mp/record/deviceOnlineInfo",
        "/mp/record/opponentStatistics",
        "/mp/coupon/checkEligibility",
    ], help="隐藏接口（默认7个轮询接口；--hide 不跟值=全部显示；--hide /path=自定义）")
    auto_parser.add_argument("--full", action="store_true", help="智能获取完整响应（小响应直接用 logcat，大响应才走 Python requests）")
    auto_parser.add_argument("--html", action="store_true", help="启动 DevTools HTML 界面")
    auto_parser.add_argument("--port", type=int, default=8765, help="HTML 服务端口 (默认 8765)")
    auto_parser.add_argument("--restart", action="store_true", default=False, help="抓包前强制重启 App（确保产生新的请求日志）")
    auto_parser.add_argument("--pkg", default=None, help="指定 App 包名（默认自动检测）")

    subparsers.add_parser("list", help="列出所有已知接口")

    args = parser.parse_args()

    # 动态注入用户身份（覆盖 server 层的默认值）
    configure(
        user_id=args.user,
        token=args.token,
        refresh_token=args.refresh_token,
    )
    if args.user:
        cprint(f"当前用户: {args.user}", Colors.CYAN)

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
