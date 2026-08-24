#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevTools 后端服务 — 抓包核心 + HTTP 服务 + HTML 托管
"""

import os
import re
import json
import time
import base64
import threading
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============== 配置（由 configure() 或 logcat 自动检测动态注入） ==============

BASE_URL = "https://test.supervisions.cn"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

USER_ID = None


def configure(user_id=None, token=None, refresh_token=None):
    """动态配置用户身份和认证信息（CLI --user / --token / --refresh-token）"""
    global USER_ID, HEADERS
    if user_id:
        USER_ID = user_id
    if token:
        HEADERS["Authorization"] = token
    if refresh_token:
        HEADERS["refresh_token"] = refresh_token


def _decode_jwt_payload(jwt_token):
    """解码 JWT payload（base64），提取 userId 等字段"""
    try:
        parts = jwt_token.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        # 补齐 base64 padding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


# 自动认证状态（logcat 抓包时从 App 请求中自动提取）
_auto_auth = {
    'detected': False,
    'user_id': None,
    'token': None,
    'refresh_token': None,
}

# HTML 文件路径（与本文件同目录下的 index.html）
_HTML_DIR = os.path.dirname(os.path.abspath(__file__))
_HTML_CACHE = {"content": None}


def get_html():
    """读取 DevTools HTML 页面（带缓存）"""
    if _HTML_CACHE["content"] is None:
        path = os.path.join(_HTML_DIR, "index.html")
        with open(path, "r", encoding="utf-8") as f:
            _HTML_CACHE["content"] = f.read()
    return _HTML_CACHE["content"]


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


_print_lock = threading.Lock()


def safe_print(text, color=None, bold=False):
    """线程安全的打印"""
    prefix = ""
    if bold:
        prefix += Colors.BOLD
    if color:
        prefix += color
    formatted = f"{prefix}{text}{Colors.RESET}"
    formatted = formatted.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
    with _print_lock:
        print(formatted)


# ============== 接口解析工具 ==============

def _dart_to_json(dart_str):
    """将 Dart 风格对象转为 JSON"""
    if not dart_str or not dart_str.strip().startswith("{"):
        return None
    s = dart_str.strip()
    inner = s[1:-1].strip() if s.endswith("}") else s[1:].strip()
    if not inner:
        return {}

    result = {}
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
    """解析请求数据"""
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
    """用 Python requests 获取完整响应（包含 status/headers/size/timing）"""
    data = None
    try:
        data = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        data = _dart_to_json(data_str)
    if data is None:
        data = {"raw": data_str[:200] if data_str else ""}

    try:
        from urllib.parse import urlparse
        parsed = urlparse(uri)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query

        if parsed.scheme == 'https':
            import http.client
            conn = http.client.HTTPSConnection(host, port, timeout=10)
        else:
            import http.client
            conn = http.client.HTTPConnection(host, port, timeout=10)

        body_bytes = json.dumps(data).encode('utf-8')
        hdrs = dict(HEADERS)
        hdrs['Content-Type'] = 'application/json'
        hdrs['Content-Length'] = str(len(body_bytes))

        t_start = time.time()
        conn.request(method.upper(), path, body=body_bytes, headers=hdrs)

        resp = conn.getresponse()
        t_first_byte = time.time()
        resp_body_raw = resp.read()
        t_end = time.time()
        conn.close()

        ttfb_ms = round((t_first_byte - t_start) * 1000, 1)
        download_ms = round((t_end - t_first_byte) * 1000, 1)
        total_ms = round((t_end - t_start) * 1000, 1)

        body = None
        try:
            body = json.loads(resp_body_raw)
        except (json.JSONDecodeError, ValueError):
            body = resp_body_raw.decode('utf-8', errors='replace')[:5000]

        size = len(resp_body_raw)

        return {
            'status': resp.status,
            'headers': dict(resp.getheaders()),
            'body': body,
            'size': size,
            'time_ms': total_ms,
            'timing': {'ttfb': ttfb_ms, 'download': download_ms},
            'error': None
        }
    except Exception as e:
        return {
            'status': 0,
            'headers': {},
            'body': None,
            'size': 0,
            'time_ms': 0,
            'timing': {},
            'error': str(e)
        }


# ============== API 记忆库 ==============

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_memory.json")


class MemoryManager:
    """线程安全的 API 记忆库管理器"""

    def __init__(self, filepath):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._cache = self._load()
        self._dirty = False
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
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except OSError:
            pass

    def _periodic_save(self):
        try:
            with self._lock:
                if self._dirty:
                    self._save_unlocked()
        except Exception:
            pass
        try:
            self._save_timer = threading.Timer(30.0, self._periodic_save)
            self._save_timer.daemon = True
            self._save_timer.start()
        except RuntimeError:
            pass

    def flush(self):
        with self._lock:
            if self._dirty:
                self._save_unlocked()

    def shutdown(self):
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
            self._save_unlocked()
            return True

    def known_urls(self):
        with self._lock:
            return {api["url"] for api in self._cache.values()}


_memory_mgr = MemoryManager(MEMORY_FILE)


# ============== 日志缓冲区 ==============

class LogBuffer:
    """线程安全的日志缓冲区，供 HTML DevTools 界面读取"""

    def __init__(self, max_size=1000):
        self._lock = threading.Lock()
        self._logs = []
        self._max_size = max_size

    def add(self, log_entry):
        with self._lock:
            self._logs.append(log_entry)
            if len(self._logs) > self._max_size:
                self._logs = self._logs[-self._max_size:]

    def get_all(self, since_id=None, method_filter=None, status_filter=None):
        with self._lock:
            logs = list(self._logs)

        if since_id is not None:
            for i, log in enumerate(logs):
                if log['id'] == since_id:
                    logs = logs[i + 1:]
                    break

        if method_filter:
            logs = [l for l in logs if l.get('method', '').upper() == method_filter.upper()]
        if status_filter:
            try:
                sc = int(status_filter)
                if sc == 2:
                    logs = [l for l in logs if 200 <= l.get('status', 0) < 300]
                elif sc == 3:
                    logs = [l for l in logs if 300 <= l.get('status', 0) < 400]
                elif sc == 4:
                    logs = [l for l in logs if 400 <= l.get('status', 0) < 500]
                elif sc == 5:
                    logs = [l for l in logs if l.get('status', 0) >= 500]
                else:
                    logs = [l for l in logs if l.get('status', 0) == sc]
            except ValueError:
                pass

        return logs

    def get_stats(self):
        with self._lock:
            total = len(self._logs)
            by_status = {}
            for log in self._logs:
                sc = log.get('status', 0)
                key = f"{sc // 100}xx" if sc else "pending"
                by_status[key] = by_status.get(key, 0) + 1
            return {
                'total': total,
                'by_status': by_status,
            }

    def clear(self):
        with self._lock:
            self._logs.clear()


log_buffer = LogBuffer()
log_id_counter = 0
log_id_lock = threading.Lock()


def next_log_id():
    global log_id_counter
    with log_id_lock:
        log_id_counter += 1
        return log_id_counter


def _safe_json_dumps(obj):
    """递归清理字符串中的孤立 surrogate，确保 json.dumps + utf-8 编码不报错"""
    def _clean(o):
        if isinstance(o, str):
            return o.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        elif isinstance(o, list):
            return [_clean(item) for item in o]
        elif isinstance(o, dict):
            return {_clean(k): _clean(v) for k, v in o.items()}
        return o
    return json.dumps(_clean(obj), ensure_ascii=False)


# ============== DevTools HTTP 服务 ==============

class HTMLRequestHandler(BaseHTTPRequestHandler):
    """DevTools HTML 界面请求处理器"""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ('/', '/index.html'):
            self.serve_html()
        elif parsed.path == '/api/logs':
            self.serve_logs_json(parsed)
        elif parsed.path == '/api/clear':
            log_buffer.clear()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_error(404)

    def serve_html(self):
        """返回 DevTools HTML 页面"""
        html = get_html()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def serve_logs_json(self, parsed):
        """返回日志 JSON 数据（支持筛选参数）"""
        params = urllib.parse.parse_qs(parsed.query)
        since_id = params.get('since', [None])[0]
        if since_id is not None:
            since_id = int(since_id)

        method_filter = params.get('method', [None])[0]
        status_filter = params.get('status', [None])[0]

        logs = log_buffer.get_all(since_id, method_filter, status_filter)
        stats = log_buffer.get_stats()

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {
            'stats': stats,
            'logs': logs
        }
        self.wfile.write(_safe_json_dumps(response).encode('utf-8'))


def start_html_server(port):
    """启动 HTML DevTools 服务，自动尝试备用端口"""
    server = None
    ports_to_try = [port, port + 1, port + 2, 8888, 9999]
    actual_port = None

    for p in ports_to_try:
        try:
            server = HTTPServer(('127.0.0.1', p), HTMLRequestHandler)
            actual_port = p
            if p != port:
                cprint(f"  端口 {port} 被占用，使用备用端口 {p}", Colors.YELLOW)
            break
        except PermissionError:
            continue
        except OSError as e:
            if "already in use" in str(e).lower() or "10048" in str(e):
                continue
            raise

    if server is None:
        raise RuntimeError(f"无法绑定端口 {port} 及其备用端口，请手动指定 --port")

    def _run_server():
        try:
            server.serve_forever()
        except Exception as e:
            safe_print(f"  HTML 服务异常: {e}", Colors.RED)

    thread = threading.Thread(target=_run_server, daemon=False)
    thread.start()
    return server, actual_port


# ============== 工具函数 ==============

def format_time(ms):
    """格式化耗时"""
    if not ms or ms <= 0:
        return '-'
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms/1000:.2f}s"


def format_size(bytes_val):
    """格式化大小"""
    if not bytes_val or bytes_val <= 0:
        return '-'
    if bytes_val < 1024:
        return f"{bytes_val}B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val/1024:.1f}KB"
    return f"{bytes_val/(1024*1024):.2f}MB"


def short_device_id(device):
    if device.startswith("adb-"):
        parts = device.split("-")
        return parts[1][:8] if len(parts) >= 2 else device[:10]
    return device[:8]
