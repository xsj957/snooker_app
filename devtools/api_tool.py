#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 抓包调试工具 v3.1
功能：实时抓包 + Chrome DevTools 风格 HTML 界面
      所有接口均走 Python HTTP 获取完整响应（含 status/headers/size/timing）

用法：python devtools/api_tool.py auto [options]

auto 参数：
  -s, --device   指定 ADB 设备 ID（多设备时必须指定，单设备自动检测）
  --hide         隐藏轮询接口（默认隐藏7个高频轮询接口；--hide 不跟值=全部显示）
  --restart      抓包前强制重启 App（确保产生新的请求日志）
  --pkg          指定 App 包名（默认自动检测国内/海外版）

示例：
  python devtools/api_tool.py auto                  # 启动抓包 + DevTools 界面
  python devtools/api_tool.py auto --restart        # 重启 App 后抓包
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
    extract_path, detect_env, get_env_label,
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


# ============== 自动模式 v3.0（DevTools 风格） ==============

def cmd_auto(args):
    """实时监控 + DevTools 风格 HTML 界面"""
    devices = getattr(args, '_devices', None)
    if not devices:
        cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
        return

    html_port = 8765
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

    cprint("模式: 全量获取（所有接口均走 Python HTTP 获取完整响应）", Colors.CYAN)

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

            path = extract_path(uri)
            env = detect_env(uri)
            env_label = get_env_label(env)
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

            # 存入日志缓冲区（HTML DevTools 界面实时读取）
            log_entry = {
                'id': next_log_id(),  # 全局唯一递增 ID，避免多设备 per-buffer seq 冲突
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'device': tag,
                'method': method,
                'path': path,
                'full_url': uri,
                'env': env,
                'env_label': env_label,
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
        完成一个请求 — 始终走 Python HTTP worker 获取完整响应（含 status/headers/size/timing）
        """
        if not buf["uri"] or not buf["method"]:
            return

        tag = short_device_id(device_id)
        data_str = " ".join(buf["data_lines"])
        req_headers = dict(buf["req_headers"]) if buf["req_headers"] else {}

        safe_print(f"\n[{tag}] ⟳ {buf['method']} {extract_path(buf['uri'])} → Python 获取完整响应...", Colors.YELLOW)
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
                # 总是尝试捕获 Response Text: 后面的内容，即使包含 [DIO]
                if after_marker:
                    # 去除 [DIO] 标记
                    clean = after_marker
                    if "[DIO]" in clean:
                        clean = clean.split("[DIO]")[-1].strip()
                    if clean and not clean.startswith("***"):
                        buf["response_lines"].append(clean)
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
                path = extract_path(buf["uri"])
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

        # 重新启动 HTTP worker（始终启动，所有接口均走 Python HTTP 获取完整响应）
        http_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="http-worker")
        worker_threads = []
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
                cprint(f"  {api['method']} {extract_path(api['uri'])}", Colors.WHITE)


# ============== CLI ==============

def main():
    parser = argparse.ArgumentParser(
        description="斯诺克大师 App API 抓包调试工具 v3.1 — DevTools 风格",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python devtools/api_tool.py auto                         # 实时监控 + DevTools 界面（推荐）
  python devtools/api_tool.py auto --restart               # 抓包前重启 App
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

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
    auto_parser.add_argument("--restart", action="store_true", default=False, help="抓包前强制重启 App（确保产生新的请求日志）")
    auto_parser.add_argument("--pkg", default=None, help="指定 App 包名（默认自动检测）")

    args = parser.parse_args()

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
        if not args._devices:
            cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
            sys.exit(1)
        cmd_auto(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
