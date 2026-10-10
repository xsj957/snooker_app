#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 抓包工具 — 精简版（纯重放）
====================================================
与完整版 api_tool.py 的区别：只从 logcat 解析"请求"信息（uri/method/body/headers），
logcat 响应段一律跳过（单条 4000 字符截断是万恶之源），
浏览器里的响应 100% 来自 Python 二次请求 = 永远完整、格式规范。

砍掉的东西：响应捕获状态机、orphan 错配缓存、截断判定、括号配平、
            历史画像分级、重放/捕获一致性比对、自动认证（重放只用捕获到的请求头，无需全局 token）

安全性保留：副作用接口（解锁/退款/注销/登录）依旧绝不重放，只展示请求。

用法：
  python devtools/api_tool_lite.py                 # 启动抓包 + DevTools 界面（默认端口 8766）
  python devtools/api_tool_lite.py --restart       # 抓包前重启 App（捕获启动链路请求）
  python devtools/api_tool_lite.py --hide          # 不隐藏任何接口
  python devtools/api_tool_lite.py --selftest      # 无需手机，自检解析器+重放链路

参数：
  -s, --device   指定 ADB 设备 ID（多设备并行；单设备自动检测）
  --hide         隐藏轮询接口（默认隐藏 8 个高频接口；--hide 不带值=全显示）
  --restart      抓包前强制重启 App
  --pkg          指定 App 包名（默认自动检测国内/海外版）
  --port         HTML 界面端口（默认 8766，可与完整版 8765 同时跑）
"""

import sys
import os

_devtools_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_devtools_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
import subprocess
import re
import json
import threading
import queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from devtools import server as _server
from devtools.server import (
    BASE_URL,
    Colors, cprint, safe_print,
    _fetch_full_response, _parse_request_data,
    log_buffer,
    start_html_server,
    format_time, format_size, short_device_id,
    next_log_id,
    extract_path, detect_env, get_env_label,
    SYS_LOG_LINE_RE,
    _norm_replay_path,
    replay_policy,
)

# 用户点名要"看响应"的接口 —— 直接写在这里，永久生效
# 注意: 写操作接口的重放响应是"第2次执行"的返回，可能与 App 当次看到的不同
EXTRA_REPLAY_ALLOW = [
    "/mp/app/deleteAlias",    # 2026-10-10 记录: 预发环境接口, 重放看响应结构/错误码
]

# ============== logcat [DIO] 请求段解析（纯请求版状态机） ==============

DIO_ANCHOR_RE = re.compile(
    r'^(?:\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s+[\w\.\-]+\s*:\s*)?\[DIO\]\s*(.*)$')

DIO_META_HEADER_KEYS = ("contenttype", "content-length", "followredirects", "responsetype")


def new_buf():
    return {
        "uri": None, "method": None,
        "data_lines": [], "req_headers": {},
        "in_data": False,
        "skip": False,       # 响应段/异常段：内容全部跳过
        "exception": False,
    }


def _parse_dart_dict(text):
    """headers: {a: b, c: d} 形态的简易解析（值统一转字符串，键名保持原样）"""
    from devtools.server import _dart_to_json
    parsed = _dart_to_json(text, scalars_as_str=True)
    return parsed if isinstance(parsed, dict) else {}


def flush_buf(device_id, buf, q):
    """产出一条请求记录（uri+method 齐备才算数），并清空 buf"""
    uri, method = buf["uri"], buf["method"]
    data_str = "".join(buf["data_lines"]).strip()
    req_headers = dict(buf["req_headers"])
    exc = buf["exception"]
    buf.clear()
    buf.update(new_buf())
    if uri and method:
        q.put({"device_id": device_id, "uri": uri, "method": method,
               "data_str": data_str, "req_headers": req_headers, "exception": exc})


def process_line(content, device_id, buf, q, hide_list):
    """单行 logcat → 只提取请求段字段；响应段整体跳过，物理上杜绝截断/错配/污染"""
    stripped = content.strip()
    m = DIO_ANCHOR_RE.match(stripped)
    if m:
        cleaned = m.group(1).strip()
    elif SYS_LOG_LINE_RE.match(stripped):
        return  # 系统日志行：丢弃
    else:
        # 无行头无 [DIO] = 多行消息续行，只有正在收集请求体时才有意义
        if buf["skip"] or not buf["in_data"]:
            return
        cleaned = stripped

    # ---- 段标记 ----
    if "*** Request ***" in cleaned:
        flush_buf(device_id, buf, q)      # 上个请求若没等到 Response 标记也照常产出
        return
    if "*** Response ***" in cleaned:
        flush_buf(device_id, buf, q)      # 请求段到此完整，正好触发重放
        buf["skip"] = True                # 之后的响应内容与本工具无关
        return
    if "*** DioException ***" in cleaned:
        buf["exception"] = True
        flush_buf(device_id, buf, q)
        return
    if cleaned.startswith("***"):
        buf["in_data"] = False
        buf["skip"] = True               # 其它 Dio 段标记：跳到下一个 Request
        return

    if buf["skip"]:
        return

    # ---- 请求段字段（data 续行优先，防请求体里的 "uri:" 字样劫持） ----
    if buf["in_data"]:
        if cleaned == "":
            buf["in_data"] = False
        else:
            buf["data_lines"].append(cleaned)
        return
    if cleaned.startswith("uri:"):
        m2 = re.search(r'uri:\s*(https?://\S+)', cleaned)
        if m2:
            uri = m2.group(1).strip()
            path_noq = extract_path(uri).split('?')[0]
            hide = bool(re.search(r'\.mp4(\?|$)', uri)) or \
                   any(path_noq == h or path_noq.startswith(h + '/') for h in hide_list)
            if not hide:
                buf["uri"] = uri
        return
    if cleaned.startswith("method:"):
        m2 = re.search(r'method:\s*(\w+)', cleaned)
        if m2:
            buf["method"] = m2.group(1).strip()
        return
    if cleaned.startswith("headers:"):
        after = cleaned.split("headers:", 1)[-1].strip()
        if after.startswith("{"):
            for k, v in _parse_dart_dict(after).items():
                if k.lower() not in DIO_META_HEADER_KEYS:
                    buf["req_headers"][k] = str(v)
        return
    if cleaned.startswith("Authorization:"):
        m2 = re.search(r'Authorization:\s*(.+)$', cleaned)
        if m2:
            buf["req_headers"]["Authorization"] = m2.group(1).strip()
        return
    if cleaned.startswith("refresh_token:"):
        m2 = re.search(r'refresh_token:\s*(.+)$', cleaned)
        if m2:
            buf["req_headers"]["refresh_token"] = m2.group(1).strip()
        return
    if cleaned.startswith("data:"):
        buf["in_data"] = True
        buf["data_lines"] = []
        after = cleaned.split("data:", 1)[-1].strip()
        if after:
            buf["data_lines"].append(after)
        return


# ============== 内置已知接口（[NEW] 标记用） ==============

BUILTIN_PATHS = {
    "/mp/user/info", "/mp/user/myClubs", "/mp/user/saveDefaultClub",
    "/mp/user/rating", "/mp/user/breakScoreList", "/mp/user/deleteAccount",
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
    "/mp/record/barchart", "/mp/record/statics", "/mp/record/simpleStatics",
    "/video/videoinfo/competitionVideos", "/video/videoinfo/buyitUseComboV3",
    "/video/videoOrder/appPostVideoRefund",
    "/mp/rank/clubList", "/mp/rank/userBreakRank",
    "/mp/rank/ratingList", "/mp/rank/breakList", "/mp/rank/winRateList",
    "/mp/event/track", "/mp/video/addVideoEventFromMobile",
}


# ============== 主流程 ==============

def cmd_lite(args):
    devices = args._devices
    hide_list = args.hide or []
    html_port = args.port

    extra_allow = list(EXTRA_REPLAY_ALLOW) + list(args.replay_allow or [])
    if extra_allow:
        _server.REPLAY_ALLOW_PATHS.update(
            _norm_replay_path(p) if p.startswith('/') else f'/{p}' for p in extra_allow)
        cprint(f"额外重放白名单: {', '.join(extra_allow)}", Colors.CYAN)

    cprint(f"精简抓包（纯重放）| 设备: {', '.join(devices)}", Colors.CYAN, bold=True)
    cprint("浏览器响应全部来自 Python 二次请求；副作用接口只展示请求、绝不重放", Colors.CYAN)
    if hide_list:
        cprint(f"已隐藏接口: {', '.join(hide_list)}", Colors.DIM)
    cprint("Ctrl+C 停止", Colors.DIM)
    print("=" * 60)

    log_buffer.reset()
    stop_event = threading.Event()
    request_q = queue.Queue()

    html_server, actual_port = start_html_server(html_port)
    cprint(f"  DevTools 界面: http://localhost:{actual_port}", Colors.GREEN, bold=True)

    seen_paths = set(BUILTIN_PATHS)
    request_count = [0]

    # ---------- 重放 worker ----------
    def worker():
        while not stop_event.is_set():
            try:
                rec = request_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                handle_record(rec)
            except Exception as e:
                safe_print(f"处理记录异常: {e}", Colors.RED)
            finally:
                request_q.task_done()

    def handle_record(rec):
        uri, method = rec["uri"], rec["method"]
        tag = short_device_id(rec["device_id"])
        path = extract_path(uri)
        path_noq = path.split('?')[0]
        env = detect_env(uri)
        prefix = f"[{tag}] "

        with seen_lock:
            is_new = path_noq not in seen_paths
            if is_new:
                seen_paths.add(path_noq)

        data, _, parse_ok = _parse_request_data(rec["data_str"])

        if rec["exception"]:
            _emit(prefix, tag, rec, path, env, is_new, None,
                  status=0, error='App 侧请求异常(DioException)，未重放')
            return

        allow, why = replay_policy(path, env)
        py = _fetch_full_response(uri, method, rec["data_str"], req_headers=rec["req_headers"]) if allow else None
        py_ok = bool(py) and py.get("error") is None

        if py_ok:
            _emit(prefix, tag, rec, path, env, is_new, py, status=py["status"], error=None)
        else:
            err = why if not allow else f"重放失败: {py['error']}"
            _emit(prefix, tag, rec, path, env, is_new, py if allow else None,
                  status=(py or {}).get("status", 0), error=err)

    def _emit(prefix, tag, rec, path, env, is_new, py, status, error):
        request_count[0] += 1
        py_ok = bool(py) and py.get("error") is None
        color = Colors.RED if error else (Colors.GREEN if is_new else Colors.BLUE)
        new_mark = " [NEW]" if is_new else ""
        safe_print(f"{prefix}>> {rec['method']} {path} [{status}]{new_mark} "
                   f"{format_size(py['size']) if py_ok else ''} {format_time(py['time_ms']) if py_ok else ''}",
                   color, bold=is_new)
        if error:
            safe_print(f"{prefix}   ⚠ {error}", Colors.YELLOW)
        if data := rec["data_str"]:
            safe_print(f"{prefix}   请求: {data[:300]}", Colors.DIM)
        if py_ok:
            body_disp = json.dumps(py["body"], ensure_ascii=False) if isinstance(py["body"], (dict, list)) else str(py["body"])
            safe_print(f"{prefix}   响应: {body_disp[:2000]}", Colors.WHITE)

        data_obj, _, parse_ok = _parse_request_data(rec["data_str"])
        log_buffer.add({
            "id": next_log_id(),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "device": tag,
            "method": rec["method"],
            "path": path,
            "full_url": rec["uri"],
            "env": env,
            "env_label": get_env_label(env),
            "status": status,
            "status_authoritative": py_ok,
            "size": py["size"] if py_ok else 0,
            "time_ms": py["time_ms"] if py_ok else 0,
            "timing": py["timing"] if py_ok else {},
            "is_new": is_new,
            "is_error": bool(error) and not py_ok,
            "request_data": data_obj if parse_ok else None,
            "request_raw": rec["data_str"] or None,
            "request_parse_ok": parse_ok,
            "request_polluted": False,
            "request_headers": rec["req_headers"],
            "response_headers": py["headers"] if py_ok else {},
            "response_body": py["body"] if py_ok else None,
            "response_raw": py["raw_text"] if py_ok else None,
            "error": None if py_ok else error,
            "source": "replay" if py_ok else "none",
            "replay_note": "重放成功" if py_ok else (error or ""),
            "replay_diff": False,
            "captured_complete": False,
            "py_complete": py_ok,
            "profile": None,
            "captured_truncated": False,
        })

    seen_lock = threading.Lock()

    # ---------- logcat 读取 ----------
    def logcat_reader(device_id):
        tag = short_device_id(device_id)
        buf = new_buf()
        try:
            proc = subprocess.Popen(
                ["adb", "-s", device_id, "logcat"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            import io as _io
            reader = _io.TextIOWrapper(proc.stdout, encoding="utf-8", errors="replace", line_buffering=True)
            for line in reader:
                if stop_event.is_set():
                    break
                process_line(line, device_id, buf, request_q, hide_list)
        except Exception as e:
            safe_print(f"  [{tag}] logcat 错误: {e}", Colors.RED)
        finally:
            flush_buf(device_id, buf, request_q)
            proc.terminate()
            safe_print(f"  [{tag}] logcat 流已结束", Colors.DIM)

    # ---------- 可选：重启 App ----------
    def detect_pkg(device_id):
        if args.pkg:
            return args.pkg
        for pkg in ("com.supervisions.snookermastercn", "com.supervisions.snookermaster"):
            try:
                r = subprocess.run(["adb", "-s", device_id, "shell", "pm", "path", pkg],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0 and "package:" in r.stdout:
                    return pkg
            except Exception:
                pass
        return None

    import time as _t
    if args.restart:
        for device_id in devices:
            tag = short_device_id(device_id)
            pkg = detect_pkg(device_id)
            if not pkg:
                safe_print(f"  [{tag}] 未检测到 App 包名，跳过重启", Colors.YELLOW)
                continue
            subprocess.run(["adb", "-s", device_id, "shell", "am", "force-stop", pkg], capture_output=True, timeout=5)
            subprocess.run(["adb", "-s", device_id, "shell", "logcat", "-c"], capture_output=True, timeout=5)
            safe_print(f"  [{tag}] 已停止 App", Colors.DIM)
    else:
        for device_id in devices:
            subprocess.run(["adb", "-s", device_id, "logcat", "-c"], capture_output=True, timeout=5)

    threads = []
    for device_id in devices:
        t = threading.Thread(target=logcat_reader, args=(device_id,), daemon=True)
        t.start()
        threads.append(t)

    if args.restart:
        _t.sleep(0.5)
        for device_id in devices:
            tag = short_device_id(device_id)
            pkg = detect_pkg(device_id)
            if not pkg:
                continue
            r = subprocess.run(["adb", "-s", device_id, "shell", "monkey", "-p", pkg,
                                "-c", "android.intent.category.LAUNCHER", "1"],
                               capture_output=True, text=True, timeout=5)
            if "No activities found" in (r.stdout or ""):
                subprocess.run(["adb", "-s", device_id, "shell", "am", "start", "-n", f"{pkg}/.MainActivity"],
                               capture_output=True, timeout=5)
            safe_print(f"  [{tag}] 已启动 App", Colors.CYAN)

    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="replay-worker")
    for _ in range(4):
        pool.submit(worker)

    try:
        while True:
            _t.sleep(0.5)
            if stop_event.is_set() or not any(t.is_alive() for t in threads):
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        pool.shutdown(wait=False)
        try:
            html_server.shutdown()
        except Exception:
            pass
    print(f"\n已停止，共处理 {request_count[0]} 个请求")


# ============== 自检（无需手机） ==============

SELFTEST_LINES = [
    # 正常请求段：头里含 Authorization，请求体多行
    "10-10 09:00:00.100 1111 2222 D flutter : [DIO] *** Request ***",
    "10-10 09:00:00.101 1111 2222 D flutter : [DIO] uri: https://test.supervisions.cn/video/videoClient/myVideos/readyV2?lang=zh_CN",
    "10-10 09:00:00.102 1111 2222 D flutter : [DIO] method: POST",
    "10-10 09:00:00.103 1111 2222 D flutter : [DIO] contentType: application/json",
    "10-10 09:00:00.104 1111 2222 D flutter : [DIO] responseType: ResponseType.json",
    "10-10 09:00:00.105 1111 2222 D flutter : [DIO] followRedirects: true",
    "10-10 09:00:00.106 1111 2222 D flutter : [DIO] headers: {Authorization: TESTTOKEN, contentType: application/json}",
    "10-10 09:00:00.107 1111 2222 D flutter : [DIO] data:",
    '{',
    '  "pageNo": 1,',
    '  "pageSize": 200,',
    '  "clientId": "a608fe50-fa8d-4718-b67c-d2eab38b93e4",',
    '  "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a",',
    '  "lang": "zh_CN"',
    '}',
    # 响应段（应被整体跳过——哪怕里面有 "uri:"、"data:" 字样也不许污染状态机）
    "10-10 09:00:00.300 1111 2222 D flutter : [DIO] *** Response ***",
    "10-10 09:00:00.301 1111 2222 D flutter : [DIO] uri: https://test.supervisions.cn/video/videoClient/myVideos/readyV2?lang=zh_CN",
    "10-10 09:00:00.302 1111 2222 D flutter : [DIO] Response Text:",
    '{"code":0,"data":{"list":[{"id":1,"uri:": "tricky"}]}}',
    # 干扰系统行
    "10-10 09:00:00.400 3333 4444 I chatty  : uid=1000 data: fake pollution",
    # 下一个请求
    "10-10 09:00:01.000 1111 2222 D flutter : [DIO] *** Request ***",
    "10-10 09:00:01.001 1111 2222 D flutter : [DIO] uri: https://test.supervisions.cn/mp/event/track",
    "10-10 09:00:01.002 1111 2222 D flutter : [DIO] method: POST",
    "10-10 09:00:01.003 1111 2222 D flutter : [DIO] data: {\"modelType\": 1}",
    "10-10 09:00:01.100 1111 2222 D flutter : [DIO] *** DioException ***",
    "10-10 09:00:01.101 1111 2222 D flutter : [DIO] uri: https://test.supervisions.cn/mp/event/track",
    # 异常段后续行必须被抑制，不得构成幻影请求
    "10-10 09:00:01.102 1111 2222 D flutter : [DIO] method: POST",
    "10-10 09:00:01.200 1111 2222 D flutter : [DIO] *** Request ***",
]


def selftest():
    """无设备自检：解析器行为 + 隐藏过滤 + 异常抑制；如提供 --selftest-token 还验证真实重放"""
    q = queue.Queue()
    buf = new_buf()
    hide = ["/mp/event/track"]  # 故意隐藏 track，验证过滤
    for line in SELFTEST_LINES:
        process_line(line, "SELFTEST", buf, q, hide)
    flush_buf("SELFTEST", buf, q)

    recs = []
    while not q.empty():
        recs.append(q.get_nowait())

    print(f"解析出 {len(recs)} 条请求记录（期望 1 条：readyV2；track 被隐藏，异常段无幻影）")
    ok = True
    if len(recs) != 1:
        ok = False
    r = recs[0] if recs else None
    checks = [
        ("uri 正确", r and r["uri"].endswith("readyV2?lang=zh_CN")),
        ("method 正确", r and r["method"] == "POST"),
        ("请求体多行拼接完整", r and json.loads(r["data_str"])["clientId"] == "a608fe50-fa8d-4718-b67c-d2eab38b93e4"),
        ("Authorization 头捕获", r and r["req_headers"].get("Authorization") == "TESTTOKEN"),
        ("响应段未污染 buf", not buf["data_lines"] and buf["uri"] is None),
    ]
    for name, passed in checks:
        print(f"  [{'✓' if passed else '✗'}] {name}")
        ok = ok and passed

    # 真实重放链路验证（用当前仍有效的测试环境 token）
    token = os.environ.get("SELFTEST_TOKEN")
    if token:
        body = json.dumps({"pageNo": 1, "pageSize": 5,
                           "clientId": "a608fe50-fa8d-4718-b67c-d2eab38b93e4",
                           "userId": "57d703dc-659a-4474-898e-b75efa1f2e0a", "lang": "zh_CN"})
        py = _fetch_full_response(
            "https://test.supervisions.cn/video/videoClient/myVideos/readyV2?lang=zh_CN",
            "POST", body, req_headers={"Authorization": token, "Content-Type": "application/json"})
        good = py.get("error") is None and py.get("status") == 200
        print(f"  [{'✓' if good else '✗'}] 真实重放 readyV2: status={py.get('status')} "
              f"size={format_size(py.get('size', 0))} time={format_time(py.get('time_ms', 0))}")
        if not good:
            print(f"      error: {py.get('error')}")
        ok = ok and good
    else:
        print("  (跳过真实重放验证：未设 SELFTEST_TOKEN 环境变量)")

    print("自检通过" if ok else "自检失败")
    return 0 if ok else 1


# ============== CLI ==============

def main():
    parser = argparse.ArgumentParser(
        description="斯诺克大师 App API 抓包 — 精简版（纯重放）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python devtools/api_tool_lite.py                # 启动（推荐先插手机）
  python devtools/api_tool_lite.py --restart      # 重启 App 抓启动链路
  python devtools/api_tool_lite.py --selftest     # 无手机自检
""")
    parser.add_argument("-s", "--device", nargs="+", default=None, help="指定 ADB 设备 ID（可多个）")
    parser.add_argument("--hide", nargs="*", default=[
        "/mobile/getUserBoxStatus",
        "/mp/user/info",
        "/mp/rank/clubList",
        "/mp/rank/userBreakRank",
        "/mp/record/deviceOnlineInfo",
        "/mp/record/opponentStatistics",
        "/mp/record/simpleStatics",
        "/mp/coupon/checkEligibility",
    ], help="隐藏接口（--hide 不带值=全部显示）")
    parser.add_argument("--restart", action="store_true", help="抓包前强制重启 App")
    parser.add_argument("--pkg", default=None, help="指定 App 包名")
    parser.add_argument("--port", type=int, default=8766, help="HTML 界面端口（默认 8766）")
    parser.add_argument("--replay-allow", nargs="*", default=[],
                        help="临时追加允许重放的接口路径（如 --replay-allow /mp/app/foo）")
    parser.add_argument("--selftest", action="store_true", help="无设备自检解析器+重放")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())

    devices = args.device
    if not devices:
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            devices = []
            for line in result.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            devices = []
    if not devices:
        cprint("未检测到 ADB 设备（可先跑 --selftest 验证工具本身）", Colors.RED)
        sys.exit(1)
    args._devices = devices
    cmd_lite(args)


if __name__ == "__main__":
    main()
