#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 抓包调试工具 v3.1
功能：实时抓包 + Chrome DevTools 风格 HTML 界面
      捕获优先（logcat 响应完整时直接采用）+ 安全接口二次请求重放补全完整响应
      混合分级重放决策（--replay-mode auto）: 历史画像(devtools/api_profile.json)
        已知小接口且捕获完整 = 零重放; 已知大/不稳定接口 = 主动重放; 捕获截断 = 必重放
      非幂等接口（解锁/退款/注销等）绝不重放；--no-replay 可完全关闭重放

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
    _dart_to_json,
    log_buffer, configure,
    start_html_server,
    format_time, format_size, short_device_id,
    next_log_id,
    extract_path, detect_env, get_env_label,
    SYS_LOG_LINE_RE, SYS_LOG_TS_RE, is_sys_log_line, is_polluted_text, replay_policy,
    _brackets_balanced, _dart_parse_complete,
    _profile_mgr, profile_key,
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


# ============== logcat Dio 协议状态机 v3.2 ==============
# 设计要点（2026-09 全面排查的根因修复）:
# 1. 系统日志行入口即丢弃、不参与任何状态迁移 —— 请求体/响应体污染的根治
# 2. 所有协议行锚定匹配(startswith)，杜绝 data:/uri: 子串被系统行或响应体劫持
# 3. in_data 在响应段开始时必重置；段结束只由 段标记/空行/括号配平 决定
# 4. 响应归属用 Response 段自带 uri: 行校验，不匹配者入 orphan 缓存等真正主人
# 5. 记录 logcat 行首时间戳，capture 路径也能产出真实耗时

DIO_META_HEADER_KEYS = ("contenttype", "content-length", "followredirects", "responsetype")

# 锚定 [DIO] 协议行: [DIO] 必须紧跟 logcat 行头(或行首)，payload 内含字面量 [DIO] 不受影响
DIO_ANCHOR_RE = re.compile(
    r'^(?:\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s+[\w\.\-]+\s*:\s*)?\[DIO\]\s*(.*)$')


class OrphanCache:
    """错配响应缓存: 键=(device_id, uri)，带 TTL/容量/完整优先/线程安全。

    并发 Dio 请求交错时，响应段可能落在别的请求窗口内；先按 resp_uri 寄存，
    等真正的主人完成时领走。TTL 防止陈旧响应被后续同 uri 请求误领。
    """

    def __init__(self, ttl=10.0, cap=64):
        self._d = OrderedDict()
        self._lock = threading.Lock()
        self.ttl = ttl
        self.cap = cap

    def put(self, key, captured):
        with self._lock:
            old = self._d.get(key)
            if old and old.get('complete') and not captured.get('complete'):
                return  # 完整捕获不被截断捕获覆盖
            ent = dict(captured)
            ent['put_at'] = time.monotonic()
            self._d[key] = ent
            self._d.move_to_end(key)
            while len(self._d) > self.cap:
                self._d.popitem(last=False)

    def pop(self, key):
        with self._lock:
            ent = self._d.pop(key, None)
        if ent is None:
            return None
        put_at = ent.pop('put_at', 0)
        if time.monotonic() - put_at > self.ttl:
            return None  # 陈旧响应丢弃，宁缺勿错
        return ent

    def clear(self):
        with self._lock:
            self._d.clear()

    def keys(self):
        with self._lock:
            return list(self._d.keys())


def new_request_buf():
    return {
        "seq": 0,
        "uri": None, "method": None,
        "data_lines": [], "req_headers": {},
        "response_lines": [], "resp_headers": {}, "resp_uri": None,
        "in_data": False, "in_response": False,
        "body_complete": False, "body_ended": False, "body_truncated": False,
        "filtered": False, "exception": False, "uri_truncated": False,
        "suppress": False,
        "max_resp_line": 0,
        "t_req": None, "t_resp_start": None, "t_resp_end": None,
    }


def _reset_response_seg(buf, ts=None):
    """Response 段开始时的统一重置清单（防漏项毒化后续判定）"""
    buf["in_response"] = "headers"
    buf["response_lines"] = []
    buf["resp_headers"] = {}
    buf["resp_uri"] = None
    buf["body_complete"] = False
    buf["body_ended"] = False
    buf["body_truncated"] = False
    buf["in_data"] = False  # 响应段开始 = 请求体收集结束
    buf["max_resp_line"] = 0
    buf["t_resp_start"] = ts
    buf["t_resp_end"] = None


def _reset_buf(buf):
    seq = buf.get("seq", 0)
    buf.update(new_request_buf())
    buf["seq"] = seq + 1


def _log_ts(content):
    m = SYS_LOG_TS_RE.match(content.strip())
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), '%m-%d %H:%M:%S.%f')
    except ValueError:
        return None


def _probe_body_complete(buf):
    """响应体拼接到当前行后尝试 JSON 完整性判定（配平即封口，拒收后续杂行）"""
    text = "".join(buf["response_lines"])
    if not text or text.lstrip()[:1] not in ('{', '['):
        return
    try:
        json.loads(text)
        buf["body_complete"] = True
    except (json.JSONDecodeError, ValueError):
        pass


def _maybe_uid_from_line(line):
    if 'userId' not in line:
        return None
    m = re.search(r'userId["\']?\s*:\s*["\']?([\w\-]+)', line)
    return m.group(1) if m else None


def process_log_line(content, device_id, buf, hide_list, on_complete, on_auth=None, orphan_cache=None):
    """处理单行 logcat — v3.2 状态机（见模块头注释）"""
    stripped = content.strip()
    m = DIO_ANCHOR_RE.match(stripped)
    if m:
        cleaned = m.group(1).strip()
    elif SYS_LOG_LINE_RE.match(stripped):
        # ① 系统日志行: 直接丢弃（不改任何状态；含回打 [DIO] 片段的系统行）
        return
    else:
        cleaned = stripped  # 多行消息续行（无行头、无 [DIO]）

    # ①b 异常段抑制: DioException 回打的 uri/method 等不得构成幻影请求
    if buf["suppress"] and "*** Request ***" not in cleaned:
        return

    ts = _log_ts(content)

    # ② 段标记
    if "*** Request ***" in cleaned:
        on_complete(buf, device_id, "next_request")
        _reset_buf(buf)
        return
    if "*** Response ***" in cleaned:
        # 上一响应段已封口但归属非当前请求时先入 orphan，防止被新段覆写丢失
        if orphan_cache is not None and buf["response_lines"] and buf["body_complete"]:
            owner = buf["resp_uri"]
            if owner and owner != buf["uri"]:
                orphan_cache.put((device_id, owner), {
                    'text': "".join(buf["response_lines"]).strip(),
                    'headers': dict(buf["resp_headers"]),
                    'complete': True,
                    't_start': buf["t_resp_start"],
                    't_end': buf["t_resp_end"],
                })
        if buf["in_response"] and not buf["body_complete"]:
            buf["body_truncated"] = True  # 上一响应未封口即来新 Response 段 = 交错/截断
        _reset_response_seg(buf, ts)
        return
    if "*** DioException ***" in cleaned:
        buf["exception"] = True
        on_complete(buf, device_id, "exception")
        _reset_buf(buf)
        buf["suppress"] = True  # 异常段后续回打行全部丢弃，直到下一个 Request 段
        return
    if cleaned.startswith("***"):
        # 其它 Dio 段标记（如 *** Dio Error ***）= 结束当前段（headers/body 都收尾）
        buf["in_data"] = False
        if buf["in_response"] in ("headers", "body"):
            buf["in_response"] = "done"
            buf["body_ended"] = True
        return

    # ③ 响应段
    if buf["in_response"] == "headers":
        if cleaned.startswith("Response Text:"):
            buf["in_response"] = "body"
            after = cleaned.split("Response Text:", 1)[-1].strip()
            if after and not after.startswith("***"):
                buf["response_lines"].append(after)
                buf["max_resp_line"] = max(buf["max_resp_line"], len(after))
                _probe_body_complete(buf)
        elif cleaned.startswith("uri:"):
            m2 = re.search(r'uri:\s*(https?://\S+)', cleaned)
            buf["resp_uri"] = m2.group(1).strip() if m2 else None
        elif cleaned:
            m2 = re.match(r'^([\w\-]+)\s*:\s*(.+)$', cleaned)
            if m2:
                buf["resp_headers"][m2.group(1).strip()] = m2.group(2).strip()
        if ts:
            buf["t_resp_end"] = ts
        return
    if buf["in_response"] == "body":
        if cleaned == "":
            buf["in_response"] = "done"
            buf["body_ended"] = True
        else:
            buf["response_lines"].append(cleaned)
            buf["max_resp_line"] = max(buf["max_resp_line"], len(cleaned))
            if ts:
                buf["t_resp_end"] = ts
            _probe_body_complete(buf)
            if buf["body_complete"]:
                buf["in_response"] = "done"
                buf["body_ended"] = True
        return
    if buf["in_response"] == "done":
        return  # 响应已封口: 后续杂行一律拒收，直到下一个段标记

    # ④ 请求段
    # 4.1 请求体续行优先（防续行里的 uri:/method: 等字样劫持状态）
    if buf["in_data"]:
        if cleaned == "":
            buf["in_data"] = False
        else:
            buf["data_lines"].append(cleaned)  # 允许 } / ] 等纯标点续片
            if on_auth:
                uid = _maybe_uid_from_line(cleaned)
                if uid:
                    on_auth('user_id', uid, device_id)
        return
    # 4.2 认证信息提取（隐藏请求也采集，保证自动认证不被轮询页饿死）
    if cleaned.startswith("Authorization:"):
        m2 = re.search(r'Authorization:\s*(.+)$', cleaned)
        if m2:
            token = m2.group(1).strip()  # 含 "Bearer <jwt>" 带空格形态
            buf["req_headers"]["Authorization"] = token
            if on_auth:
                on_auth('token', token, device_id)
        return
    if cleaned.startswith("refresh_token:"):
        m2 = re.search(r'refresh_token:\s*(.+)$', cleaned)
        if m2:
            rt = m2.group(1).strip()
            buf["req_headers"]["refresh_token"] = rt
            if on_auth:
                on_auth('refresh', rt, device_id)
        return
    # 4.3 uri（含隐藏/mp4 过滤，精确路径匹配）
    if cleaned.startswith("uri:"):
        m2 = re.search(r'uri:\s*(https?://\S+)', cleaned)
        if m2:
            uri = m2.group(1).strip()
            if len(content) >= 4000:
                buf["uri_truncated"] = True  # logcat 单行截断嫌疑
            if re.search(r'\.mp4(\?|$)', uri):
                buf["filtered"] = True
                buf["uri"] = None
            else:
                path_noq = extract_path(uri).split('?')[0]
                if any(path_noq == h or path_noq.startswith(h + '/') for h in hide_list):
                    buf["filtered"] = True
                    buf["uri"] = None
                else:
                    buf["uri"] = uri
        return
    if buf["filtered"]:
        return  # 隐藏请求不占 buf 任何字段，避免污染下一个可见请求
    if cleaned.startswith("method:"):
        m2 = re.search(r'method:\s*(\w+)', cleaned)
        if m2:
            buf["method"] = m2.group(1).strip()
        if ts:
            buf["t_req"] = ts
        return
    if cleaned.startswith("headers:"):
        after = cleaned.split("headers:", 1)[-1].strip()
        if after.startswith("{"):
            parsed = _dart_to_json(after, scalars_as_str=True)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if k.lower() not in DIO_META_HEADER_KEYS:
                        buf["req_headers"][k] = str(v)
        return
    if cleaned.startswith("data:") and not buf["in_data"]:
        buf["in_data"] = True
        buf["data_lines"] = []
        after = cleaned.split("data:", 1)[-1].strip()
        if after:
            buf["data_lines"].append(after)
        return


def decide_replay(allow, cap_ok, pclass, mode='auto'):
    """混合分级重放决策（方案 C 矩阵）:

    - 安全闸门不通过 → 不重放
    - always  → 允许即重放（旧行为）
    - reactive→ 仅捕获不完整时重放（方案 A）
    - auto    → 捕获不完整必重放; 捕获完整时仅 known-large/unstable 主动重放
                （拿实测 status/耗时 + DIFF 一致性校验），known-small 与未知接口零重放
    """
    if not allow:
        return False
    if mode == 'always':
        return True
    if mode == 'reactive':
        return not cap_ok
    if not cap_ok:
        return True
    return pclass in ('large', 'unstable')


def finalize_buf(buf, device_id, reason, orphan_cache):
    """产出一条捕获记录; 响应归属经 resp_uri 校验, 不匹配者入 orphan 缓存。"""
    captured = None
    if buf["response_lines"]:
        text = "".join(buf["response_lines"]).strip()
        head = text[:1]
        line_trunc = buf["max_resp_line"] >= 4000  # logcat 单条载荷上限嫌疑
        if head in '{[':
            # JSON/Dart 字面量: 封口/配平/完全消费/无截断嫌疑 四重判定
            # 配平必查: 截断串在 EOF 处也会被解析器"消费完"，仅靠消费判定会把半截体判完整
            complete = bool(buf["body_complete"]) or (
                not buf["body_truncated"] and not line_trunc
                and _brackets_balanced(text) and _dart_parse_complete(text))
        else:
            cl = (buf["resp_headers"].get('content-length') or '').strip()
            cl_ok = (not cl.isdigit()) or int(cl) == len(text.encode('utf-8'))
            complete = bool(text) and bool(buf["body_ended"]) and not line_trunc and cl_ok
        captured = {
            'text': text,
            'headers': dict(buf["resp_headers"]),
            'complete': complete and not buf["body_truncated"],
            't_start': buf["t_resp_start"],
            't_end': buf["t_resp_end"],
        }
    uri = buf["uri"]
    if captured is not None and buf["resp_uri"] and uri and buf["resp_uri"] != uri:
        if orphan_cache is not None:
            orphan_cache.put((device_id, buf["resp_uri"]), captured)  # 响应属于别的请求
        captured = None
    if not uri:
        if buf["resp_uri"] and captured is not None and orphan_cache is not None:
            orphan_cache.put((device_id, buf["resp_uri"]), captured)  # 落进隐藏窗口的可见响应
        return None
    if not buf["method"]:
        return None
    if captured is None and orphan_cache is not None:
        captured = orphan_cache.pop((device_id, uri))
    return {
        'seq': buf["seq"], 'device_id': device_id, 'uri': uri, 'method': buf["method"],
        'data_str': "".join(buf["data_lines"]).strip(),
        'req_headers': dict(buf["req_headers"]),
        'captured': captured, 'reason': reason,
        'exception': buf["exception"], 'uri_truncated': buf["uri_truncated"],
        't_req': buf["t_req"],
    }


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
    no_replay = getattr(args, 'no_replay', False)
    only_python = getattr(args, 'only_python', False)
    replay_mode = getattr(args, 'replay_mode', 'auto')

    if len(devices) > 1:
        cprint(f"自动监控模式 v3.0 | {len(devices)} 台设备并行", Colors.CYAN, bold=True)
        for d in devices:
            tag = f"[{short_device_id(d)}]"
            cprint(f"  {tag} {d}", Colors.DIM)
    else:
        cprint(f"自动监控模式 v3.0 | 设备: {devices[0]}", Colors.CYAN, bold=True)

    if no_replay:
        cprint("模式: 纯被动抓包（--no-replay，绝不发二次请求；截断响应不补全）", Colors.CYAN)
    else:
        cprint("模式: 捕获优先 + 安全接口重放补全（副作用接口不重放）", Colors.CYAN)
    if only_python:
        cprint("界面过滤: 浏览器只显示 Python 解析到完整响应的接口（--only-python）", Colors.CYAN)
    cprint(f"重放决策: {replay_mode}（auto=混合分级: 已知小接口零重放/已知大接口主动重放/截断必重放）", Colors.CYAN)

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
    # known 判定用 path（不含 query）归一集合，避免 ?lang=zh_CN 使内置接口永远判"新"
    known_paths = {extract_path(u).split('?')[0] for u in known_urls}

    # v3.2 会话状态: 错配响应缓存(线程安全+TTL) / 重放节流表+锁
    orphan_cache = OrphanCache()
    _replay_last = {}
    _replay_lock = threading.Lock()
    if getattr(args, 'replay_allow', None):
        _server.REPLAY_ALLOW_PATHS.update(p if p.startswith('/') else f'/{p}' for p in args.replay_allow)

    state_lock = threading.Lock()
    seen_uris = set(known_urls)
    discovered_apis = []
    request_count = [0]

    # request_q / display_q / stop_event 在重连循环内每次重建
    # 防止旧 worker 线程在新会话中复活（stop_event.clear() 不会唤醒它们）

    def http_worker():
        """异步 HTTP Worker v3.2: 捕获优先(仅当响应完整)，安全接口重放补全完整响应与真实元数据。

        与抓包信息保持一致的手段:
        - 响应体: 捕获完整时用捕获原文(真实); 捕获截断/缺失时才用重放响应;
        - 重放请求: 由 _fetch_full_response 按捕获原文字节级重建(body/headers/query);
        - 两者都在时做归一化 JSON 比对, 不一致打 replay_diff 标记;
        - 副作用接口/污染体/uri 截断/App 侧异常 一律不重放。
        """
        while not stop_event.is_set():
            try:
                rec = request_q.get(timeout=0.5)
            except queue.Empty:
                continue

            uri = rec['uri']
            method = rec['method']
            device_id = rec['device_id']
            data_str = rec['data_str']
            req_headers = rec['req_headers']
            captured = rec['captured']

            # orphan 宽限: 并发突发时响应段可能比本记录派发晚到（错配寄存），
            # 等最多 1s 领回属于自己的真实捕获，避免本可捕获的响应退化成重放/空
            if captured is None:
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    ent = orphan_cache.pop((device_id, uri))
                    if ent is not None:
                        captured = ent
                        break
                    time.sleep(0.1)

            path = extract_path(uri)
            env = detect_env(uri)
            polluted = is_polluted_text(data_str)
            cap_ok = bool(captured and captured['complete'] and captured['text'])

            allow, why = replay_policy(path, env, no_replay=no_replay)
            if rec['uri_truncated']:
                allow, why = False, 'uri 疑似被 logcat 截断'
            if polluted:
                allow, why = False, '请求体被污染，拒绝重放'
            if rec['exception']:
                allow, why = False, 'App 侧请求异常(DioException)'

            # 混合分级决策（方案 C）: 安全闸门 → 当次完整性 → 历史画像
            pkey = profile_key(uri, method)
            profile = _profile_mgr.get(pkey)
            pclass = profile['class'] if profile else None
            replay_now = decide_replay(allow, cap_ok, pclass, replay_mode)
            rkey = f"{method} {uri}"
            py = None
            if replay_now:
                with _replay_lock:
                    now = time.monotonic()
                    if now - _replay_last.get(rkey, 0) < 1.5:
                        replay_now = False
                        why = '重放节流(同接口 1.5s 内)'
                    else:
                        _replay_last[rkey] = now
            if replay_now:
                py = _fetch_full_response(uri, method, data_str, req_headers=req_headers)
            py_ok = bool(py) and py.get('error') is None

            if py_ok:
                replay_note = why + (('; ' + py['body_note']) if py.get('body_note') else '')
            elif allow and py:
                replay_note = f"重放失败: {py['error']}（元数据以抓包为准）"
            else:
                replay_note = why

            if cap_ok:
                raw_text = captured['text']
                try:
                    body = json.loads(raw_text)
                except (json.JSONDecodeError, ValueError):
                    # Dart toString 形态（无引号键）也转成结构供 Preview 树渲染；原文仍在 response_raw
                    dart = _dart_to_json(raw_text)
                    body = dart if isinstance(dart, (dict, list)) else raw_text
            elif py is not None and py.get('raw_text') is not None:
                raw_text = py['raw_text']
                body = py['body']
            elif captured is not None and captured['text']:
                raw_text = captured['text']  # 截断原文，UI 标"截断"
                body = raw_text
            else:
                raw_text = None
                body = None

            # 一致性校验: 捕获体与重放体都在时做归一化比对
            replay_diff = False
            if cap_ok and py_ok and py.get('body') is not None and body is not None:
                try:
                    replay_diff = json.dumps(body, sort_keys=True, ensure_ascii=False) != \
                        json.dumps(py['body'], sort_keys=True, ensure_ascii=False)
                except (TypeError, ValueError):
                    replay_diff = str(body) != str(py['body'])

            # 捕获路径真实状态码: Dio 响应段的 status-code 头（无法重放时的唯一真值）
            cap_status = 0
            if captured:
                # Dio 响应头键名为驼峰(statusCode)，大小写不敏感查找
                for hk, hv in (captured['headers'] or {}).items():
                    if hk.lower() in ('status-code', 'statuscode', 'status') \
                            and str(hv).strip().isdigit():
                        cap_status = int(str(hv).strip())
                        break
            status = py['status'] if py_ok else (cap_status or (200 if cap_ok else 0))
            status_authoritative = bool(py_ok) or bool(cap_status)
            headers = (py['headers'] if py_ok else (captured['headers'] if captured else {})) or {}
            time_ms = 0
            timing = {}
            if py_ok:
                time_ms = py['time_ms']
                timing = py['timing']
            elif captured:
                t_req = rec.get('t_req')
                if t_req and captured.get('t_end'):
                    time_ms = round((captured['t_end'] - t_req).total_seconds() * 1000, 1)
                    timing = {'source': 'logcat: 请求标记→响应末行'}
                elif captured.get('t_start') and captured.get('t_end'):
                    time_ms = round((captured['t_end'] - captured['t_start']).total_seconds() * 1000, 1)
                    timing = {'source': 'logcat: 仅响应段'}
            size = py['size'] if py_ok else (len(raw_text.encode('utf-8')) if raw_text else 0)
            # 画像回写: 展示体字节数 / 捕获是否截断 / 是否走了重放（驱动下次分级决策）
            if raw_text:
                _profile_mgr.observe(
                    pkey, size,
                    truncated=bool(captured and captured['text'] and not captured['complete']),
                    replayed=py_ok)
            if cap_ok and py_ok:
                source = 'merged'
            elif cap_ok:
                source = 'logcat'
            elif py_ok:
                source = 'replay'
            elif captured and captured['text']:
                source = 'logcat-truncated'
            else:
                source = 'none'

            display_q.put({
                'seq': rec['seq'], 'device_id': rec['device_id'],
                'uri': uri, 'method': method, 'data_str': data_str, 'req_headers': req_headers,
                'status': status, 'status_authoritative': status_authoritative,
                'headers': headers, 'body': body, 'raw_text': raw_text, 'size': size,
                'time_ms': time_ms, 'timing': timing,
                'error': None if (cap_ok or py_ok) else '未捕获到响应且重放被拒绝',
                'source': source, 'replay_note': replay_note,
                'replay_diff': replay_diff, 'captured_complete': cap_ok,
                'py_complete': py_ok,
                'profile': profile,
                'captured_truncated': bool(captured and captured['text'] and not captured['complete']),
                'request_polluted': polluted, 'exception': rec['exception'],
            })
            request_q.task_done()

    def display_worker():
        """显示 Worker v3.2: 消费 http_worker 的合并记录，单次解析请求体，落日志缓冲区"""
        while not stop_event.is_set():
            try:
                item = display_q.get(timeout=0.5)
            except queue.Empty:
                continue

            device_id = item['device_id']
            uri = item['uri']
            method = item['method']
            data_str = item['data_str']
            req_headers = item['req_headers']
            status_code = item['status']
            resp_headers = item['headers']
            resp_body = item['body']
            resp_raw = item['raw_text']
            resp_size = item['size']
            time_ms = item['time_ms']
            timing_info = item['timing']
            error = item['error']

            tag = short_device_id(device_id)
            # 请求体只解析一次，展示与记忆库共用同一结果
            data, _, parse_ok = _parse_request_data(data_str)

            with state_lock:
                is_new = uri not in seen_uris
                if is_new:
                    seen_uris.add(uri)
                    # 过滤 CDN 视频原片，不进入已发现列表
                    if not re.search(r'\.mp4(\?|$)', uri):
                        discovered_apis.append({"uri": uri, "method": method, "data": data_str})
                request_count[0] += 1
                # known 判定按 path（不含 query）归一，避免 ?lang=zh_CN 使内置接口永远"新"
                is_known = uri in known_urls or extract_path(uri).split('?')[0] in known_paths

            path = extract_path(uri)
            env = detect_env(uri)
            env_label = get_env_label(env)
            prefix = f"[{tag}] "
            is_error = error is not None

            # HTTP worker 获取的完整响应 — 终端输出
            if is_error:
                safe_print(f"{prefix}!! {method} {path} [{status_code}] ({item['replay_note']})", Colors.RED, bold=True)
            elif is_new:
                safe_print(f"{prefix}>> {method} {path} [{status_code}] [NEW] 来源={item['source']}", Colors.GREEN, bold=True)
            else:
                safe_print(f"{prefix}>> {method} {path} [{status_code}] 来源={item['source']}", Colors.BLUE)
            if item['replay_diff']:
                safe_print(f"{prefix}   ⚠ 重放响应与抓包响应不一致（服务端状态已变化），以抓包为准", Colors.YELLOW)
            if item['request_polluted']:
                safe_print(f"{prefix}   ⚠ 请求体混入系统日志（历史污染数据），仅供参考", Colors.YELLOW)

            if data and parse_ok:
                data_display = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, (dict, list)) else str(data)
                safe_print(f"{prefix}   请求: {data_display}", Colors.DIM)
            elif data_str:
                safe_print(f"{prefix}   请求原文(不可解析): {data_str[:200]}", Colors.DIM)

            if resp_body is not None and not is_error:
                resp_display = json.dumps(resp_body, ensure_ascii=False, indent=2) if isinstance(resp_body, (dict, list)) else str(resp_body)
                safe_print(f"{prefix}   响应 [{status_code}] ({format_time(time_ms)}, {format_size(resp_size)}):\n{resp_display}", Colors.WHITE)
            elif is_error:
                safe_print(f"{prefix}   响应: (请求异常: {error})", Colors.RED)
            else:
                safe_print(f"{prefix}   响应: (空)", Colors.DIM)

            # 存入记忆库（污染体/不可解析体不写库）
            if not is_known and parse_ok and not item['request_polluted']:
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
                'status_authoritative': item['status_authoritative'],
                'size': resp_size,
                'time_ms': time_ms,
                'timing': timing_info,
                'is_new': is_new,
                'is_error': is_error,
                'request_data': data if (data and parse_ok) else None,
                'request_raw': data_str or None,
                'request_parse_ok': parse_ok,
                'request_polluted': item['request_polluted'],
                'request_headers': req_headers,
                'response_headers': resp_headers or {},
                'response_body': resp_body,
                'response_raw': resp_raw,
                'error': error,
                'source': item['source'],
                'replay_note': item['replay_note'],
                'replay_diff': item['replay_diff'],
                'captured_complete': item['captured_complete'],
                'captured_truncated': item['captured_truncated'],
                'py_complete': item['py_complete'],
                'profile': item.get('profile'),
            }
            # --only-python: 浏览器界面只保留 Python 二次请求解析到完整响应的条目
            if not (only_python and not item['py_complete']):
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

    def _on_complete(buf, device_id, reason):
        """状态机完成回调: 产出捕获记录入队（响应归属校验在 finalize_buf 内）"""
        rec = finalize_buf(buf, device_id, reason, orphan_cache)
        if rec:
            request_q.put(rec)

    def _on_auth(kind, value, device_id):
        """状态机认证捕获回调: token / refresh_token / userId"""
        should = False
        with _auto_auth_lock:
            if _auto_auth['detected']:
                return
            if kind == 'token' and not _auto_auth['token']:
                _auto_auth['token'] = value
                jwt = value[7:].strip() if value.lower().startswith('bearer ') else value
                payload = _decode_jwt_payload(jwt)
                if payload.get('userId'):
                    _auto_auth['user_id'] = payload['userId']
                should = True
            elif kind == 'refresh' and not _auto_auth['refresh_token']:
                _auto_auth['refresh_token'] = value
                should = True
            elif kind == 'user_id' and not _auto_auth['user_id']:
                _auto_auth['user_id'] = value
                should = True
        if should:
            _try_auto_auth(short_device_id(device_id))

    def process_line(content, device_id, buf):
        """logcat 行入口 — 委托模块级 v3.2 状态机"""
        process_log_line(content, device_id, buf, hide_list, _on_complete, _on_auth, orphan_cache)

    def logcat_reader(device_id):
        """logcat 读取线程"""
        adb_cmd = ["adb", "-s", device_id, "logcat"]
        tag = short_device_id(device_id)
        proc = None

        # 启动流式读取前，先排空设备端 logcat 环形缓冲区中的残留历史条目
        # adb logcat -c 清空后，USB 管道可能仍残留旧数据；-d 模式一次性读走这些残留
        # --restart 模式下跳过排空（已手动清空 logcat，需要保留 App 启动时的新日志）
        if not restart_app:
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

        buf = new_request_buf()

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
            _on_complete(buf, device_id, "flush")
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

        # 清空上一次会话的 HTML 缓冲 / 错配响应缓存 / 节流表（防跨会话误领）
        log_buffer.clear()
        orphan_cache.clear()
        _replay_last.clear()

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
            html_server = None
            time.sleep(1.0)  # 等待端口完全释放
        try:
            html_server, actual_port = start_html_server(html_port)
            cprint(f"  DevTools 界面: http://localhost:{actual_port}", Colors.GREEN, bold=True)
        except Exception as e:
            cprint(f"  HTML 服务启动失败: {e}", Colors.RED)

        # ============== 启动顺序：先开 logcat 流，再启动 App ==============
        # 确保 App 启动时的所有请求都被捕获（adb logcat 只读取新产生的日志）

        # 第一步：清空 logcat 缓冲区（--restart 模式下同时停止 App）
        if restart_app:
            for device_id in devices:
                tag = short_device_id(device_id)
                pkg = _detect_pkg(device_id)
                if not pkg:
                    safe_print(f"  [{tag}] 未检测到 App 包名，跳过重启", Colors.YELLOW)
                    continue
                try:
                    subprocess.run(
                        ["adb", "-s", device_id, "shell", "am", "force-stop", pkg],
                        capture_output=True, timeout=5,
                    )
                    safe_print(f"  [{tag}] 已停止 App", Colors.DIM)
                    subprocess.run(
                        ["adb", "-s", device_id, "shell", "logcat", "-c"],
                        capture_output=True, timeout=5,
                    )
                except Exception as e:
                    safe_print(f"  [{tag}] 停止 App 失败: {e}", Colors.RED)
        else:
            for device_id in devices:
                tag = short_device_id(device_id)
                try:
                    subprocess.run(["adb", "-s", device_id, "logcat", "-c"],
                                   capture_output=True, timeout=5)
                    safe_print(f"  [{tag}] 已清空 logcat 缓冲区", Colors.DIM)
                except Exception:
                    pass

        # 第二步：启动 logcat 流式读取（此时缓冲区已清空，开始监听新日志）
        logcat_threads = []
        for device_id in devices:
            t = threading.Thread(target=logcat_reader, args=(device_id,), daemon=True)
            t.start()
            logcat_threads.append(t)

        # 第三步：--restart 模式下启动 App（logcat 已在监听，不会漏掉启动请求）
        if restart_app:
            time.sleep(0.5)  # 等待 logcat 流稳定
            for device_id in devices:
                tag = short_device_id(device_id)
                pkg = _detect_pkg(device_id)
                if not pkg:
                    continue
                try:
                    result = subprocess.run(
                        ["adb", "-s", device_id, "shell", "monkey", "-p", pkg,
                         "-c", "android.intent.category.LAUNCHER", "1"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if "No activities found" in (result.stdout or ""):
                        subprocess.run(
                            ["adb", "-s", device_id, "shell", "am", "start",
                             "-n", f"{pkg}/.MainActivity"],
                            capture_output=True, timeout=5,
                        )
                    safe_print(f"  [{tag}] 已启动 App，等待 3 秒...", Colors.CYAN)
                    time.sleep(3)
                except Exception as e:
                    safe_print(f"  [{tag}] 启动 App 失败: {e}", Colors.RED)

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
        _profile_mgr.flush()

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

    # 关闭记忆库/画像库定时器，防止 Timer 线程泄漏
    _memory_mgr.shutdown()
    _profile_mgr.shutdown()

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
        "/mp/record/simpleStatics",
        "/mp/coupon/checkEligibility",
    ], help="隐藏接口（默认8个轮询接口；--hide 不跟值=全部显示；--hide /path=自定义）")
    auto_parser.add_argument("--restart", action="store_true", default=False, help="抓包前强制重启 App（确保产生新的请求日志）")
    auto_parser.add_argument("--pkg", default=None, help="指定 App 包名（默认自动检测）")
    auto_parser.add_argument("--no-replay", action="store_true", default=False,
                             help="纯被动抓包: 绝不发二次请求（最保真，截断响应不补全）")
    auto_parser.add_argument("--replay-allow", nargs="*", default=None,
                             help="额外允许重放的路径（追加到内置只读白名单，如 /mp/record/statics）")
    auto_parser.add_argument("--only-python", action="store_true", default=False,
                             help="浏览器界面只显示 Python 二次请求解析到完整响应的接口"
                                  "（副作用禁放接口与重放失败条目不进入界面）")
    auto_parser.add_argument("--replay-mode", choices=["auto", "reactive", "always"], default="auto",
                             help="重放决策模式: auto=混合分级(已知小接口零重放/已知大接口主动重放/截断必重放, "
                                  "历史画像存于 devtools/api_profile.json); reactive=仅捕获不完整时重放; "
                                  "always=允许即重放(旧行为)")

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
