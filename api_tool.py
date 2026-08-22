#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
斯诺克大师 App API 抓包调试工具 v2.0
功能：实时抓包 + 异步解析 + HTML实时查看
用法：python api_tool.py <command> [options]

命令：
  log     - 实时查看 App 网络日志（类似 tail -f | grep）
  extract - 从日志文件提取所有 API 接口信息
  call    - 调用指定接口并显示完整响应
  auto    - 实时监控 + 自动发现新接口 + 异步获取完整响应
  list    - 列出所有已发现的接口

全局参数：
  -s, --device  指定 ADB 设备 ID（多设备时必须指定）
                设备 ID 可通过 adb devices 查看
                示例：python api_tool.py auto -s 设备ID

auto 专用参数：
  --full        异步获取完整响应（Python requests 调用，绕过 logcat 截断）
                示例：python api_tool.py auto --full
  --html        启动 HTML 实时查看界面（浏览器访问 http://localhost:8765）
                示例：python api_tool.py auto --full --html
  --port        HTML 服务端口（默认 8765）
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
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# ============== 配置 ==============

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
    """用 Python requests 获取完整响应"""
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


# ============== HTML 实时日志服务 ==============

class LogBuffer:
    """线程安全的日志缓冲区，供 HTML 服务读取"""

    def __init__(self, max_size=500):
        self._lock = threading.Lock()
        self._logs = []
        self._max_size = max_size

    def add(self, log_entry):
        with self._lock:
            self._logs.append(log_entry)
            if len(self._logs) > self._max_size:
                self._logs = self._logs[-self._max_size:]

    def get_all(self, since_id=None):
        with self._lock:
            if since_id is None:
                return list(self._logs)
            # 返回 since_id 之后的日志
            for i, log in enumerate(self._logs):
                if log['id'] == since_id:
                    return self._logs[i+1:]
            return list(self._logs)


log_buffer = LogBuffer()
log_id_counter = 0
log_id_lock = threading.Lock()


def next_log_id():
    global log_id_counter
    with log_id_lock:
        log_id_counter += 1
        return log_id_counter


class HTMLRequestHandler(BaseHTTPRequestHandler):
    """HTML 服务请求处理器"""

    def log_message(self, format, *args):
        """禁用默认日志"""
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/' or parsed.path == '/index.html':
            self.serve_html()
        elif parsed.path == '/api/logs':
            self.serve_logs_json()
        else:
            self.send_error(404)

    def serve_html(self):
        """返回 HTML 页面"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>API 抓包实时日志</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
        h1 { color: #4ec9b0; font-size: 24px; }
        .stats { background: #252526; padding: 10px; border-radius: 4px; margin-bottom: 20px; }
        .log-entry { background: #252526; margin: 10px 0; padding: 12px; border-radius: 4px; border-left: 3px solid #007acc; }
        .log-entry.new { border-left-color: #4ec9b0; }
        .log-entry.error { border-left-color: #f48771; }
        .method { color: #569cd6; font-weight: bold; }
        .path { color: #ce9178; }
        .timestamp { color: #808080; font-size: 12px; }
        .device { color: #dcdcaa; font-size: 12px; }
        .tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin-left: 8px; }
        .tag-new { background: #4ec9b0; color: #1e1e1e; }
        .tag-error { background: #f48771; color: #1e1e1e; }
        .section { margin-top: 10px; }
        .section-title { color: #9cdcfe; font-weight: bold; margin-bottom: 5px; }
        pre { background: #1e1e1e; padding: 10px; border-radius: 3px; overflow-x: auto; font-size: 12px; line-height: 1.4; }
        .request-data { color: #d4d4d4; }
        .response-data { color: #d4d4d4; }
        .loading { text-align: center; padding: 40px; color: #808080; }
    </style>
</head>
<body>
    <h1>🔍 API 抓包实时日志</h1>
    <div class="stats" id="stats">加载中...</div>
    <div id="logs">
        <div class="loading">等待抓包数据...</div>
    </div>

    <script>
        let lastId = null;
        let allLogs = [];

        async function fetchLogs() {
            try {
                const url = lastId ? `/api/logs?since=${lastId}` : '/api/logs';
                const resp = await fetch(url);
                const data = await resp.json();

                if (data.logs && data.logs.length > 0) {
                    allLogs = [...allLogs, ...data.logs];
                    if (allLogs.length > 200) allLogs = allLogs.slice(-200);
                    lastId = data.logs[data.logs.length - 1].id;
                    renderLogs();
                }

                document.getElementById('stats').innerHTML = `
                    <strong>总请求数:</strong> ${data.total} |
                    <strong>新接口:</strong> ${data.new_count} |
                    <strong>最后更新:</strong> ${new Date().toLocaleTimeString()}
                `;
            } catch (e) {
                console.error('Fetch error:', e);
            }
        }

        function renderLogs() {
            const container = document.getElementById('logs');
            if (allLogs.length === 0) {
                container.innerHTML = '<div class="loading">等待抓包数据...</div>';
                return;
            }

            container.innerHTML = allLogs.slice().reverse().map(log => {
                const isNew = log.is_new ? '<span class="tag tag-new">NEW</span>' : '';
                const isError = log.is_error ? '<span class="tag tag-error">ERROR</span>' : '';
                const entryClass = log.is_error ? 'error' : (log.is_new ? 'new' : '');

                const reqData = log.request_data ? `<pre class="request-data">${escapeHtml(log.request_data)}</pre>` : '';
                const respData = log.response_data ? `<pre class="response-data">${escapeHtml(log.response_data)}</pre>` : '';

                return `
                    <div class="log-entry ${entryClass}">
                        <div>
                            <span class="timestamp">${log.timestamp}</span>
                            <span class="device">[${log.device}]</span>
                            <span class="method">${log.method}</span>
                            <span class="path">${log.path}</span>
                            ${isNew}${isError}
                        </div>
                        ${reqData ? `<div class="section"><div class="section-title">📤 请求参数</div>${reqData}</div>` : ''}
                        ${respData ? `<div class="section"><div class="section-title">📥 响应数据</div>${respData}</div>` : ''}
                    </div>
                `;
            }).join('');
        }

        function escapeHtml(text) {
            const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
            return text.replace(/[&<>"']/g, m => map[m]);
        }

        // 每 2 秒刷新
        setInterval(fetchLogs, 2000);
        fetchLogs();
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def serve_logs_json(self):
        """返回日志 JSON 数据"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        since_id = params.get('since', [None])[0]

        logs = log_buffer.get_all(since_id)

        # 统计信息
        total = len(log_buffer.get_all())
        new_count = sum(1 for log in log_buffer.get_all() if log.get('is_new'))

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {
            'total': total,
            'new_count': new_count,
            'logs': logs
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))


def start_html_server(port):
    """启动 HTML 服务，自动尝试备用端口"""
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

    # 非 daemon 线程，异常不会被吞掉
    def _run_server():
        try:
            server.serve_forever()
        except Exception as e:
            safe_print(f"  HTML 服务异常: {e}", Colors.RED)

    thread = threading.Thread(target=_run_server, daemon=False)
    thread.start()
    return server, actual_port


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
            "data": {"userId": USER_ID}
        },
        "box": {
            "name": "获取盒子状态",
            "method": "POST",
            "url": f"{BASE_URL}/mobile/getUserBoxStatus",
            "data": {"userId": USER_ID}
        },
        "version": {
            "name": "检查版本",
            "method": "POST",
            "url": f"{BASE_URL}/mp/app/version/check",
            "data": {"platform": 2, "currentVersion": "1.0.0", "userId": USER_ID}
        },
        "coupon": {
            "name": "检查视频券",
            "method": "POST",
            "url": f"{BASE_URL}/mp/coupon/checkEligibility",
            "data": {"userId": USER_ID}
        },
        "matches": {
            "name": "对手列表和视频",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/opponentListWithVideos",
            "data": {"userId": USER_ID}
        },
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

def cmd_list(args):
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

    cprint(f"\n调用示例: python api_tool.py call user", Colors.DIM)


# ============== 自动模式 v2.0（异步 + HTML） ==============

def _short_device_id(device):
    if device.startswith("adb-"):
        parts = device.split("-")
        return parts[1][:8] if len(parts) >= 2 else device[:10]
    return device[:8]


def cmd_auto(args):
    """实时监控 + 异步解析 + HTML 实时查看"""
    devices = getattr(args, '_devices', None)
    if not devices:
        cprint("未检测到 ADB 设备，请检查连接", Colors.RED)
        return

    full_mode = getattr(args, 'full', False)
    html_mode = getattr(args, 'html', False)
    html_port = getattr(args, 'port', 8765)
    hide_list = getattr(args, 'hide', []) or []

    if len(devices) > 1:
        cprint(f"自动监控模式 v2.0 | {len(devices)} 台设备并行", Colors.CYAN, bold=True)
        for d in devices:
            tag = f"[{_short_device_id(d)}]"
            cprint(f"  {tag} {d}", Colors.DIM)
    else:
        cprint(f"自动监控模式 v2.0 | 设备: {devices[0]}", Colors.CYAN, bold=True)

    if full_mode:
        cprint("模式: 异步获取完整响应（仅展示解析完成的结果）", Colors.CYAN)
    else:
        cprint("模式: logcat 监听（大响应可能截断）", Colors.CYAN)

    if html_mode:
        try:
            html_server, actual_port = start_html_server(html_port)
            cprint(f"HTML 实时查看: http://localhost:{actual_port}", Colors.GREEN, bold=True)
        except Exception as e:
            cprint(f"HTML 服务启动失败: {e}", Colors.RED)
            html_mode = False

    if hide_list:
        cprint(f"已隐藏接口: {', '.join(hide_list)}", Colors.DIM)
    cprint("Ctrl+C 停止", Colors.DIM)
    cprint("=" * 60)

    # 初始化
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

    state_lock = threading.Lock()
    seen_uris = set(known_urls)
    discovered_apis = []
    request_count = [0]

    request_q = queue.Queue()
    display_q = queue.Queue()
    stop_event = threading.Event()

    def http_worker():
        """异步获取完整响应"""
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

    def display_worker():
        """显示 Worker：只展示完整解析的响应"""
        while not stop_event.is_set():
            try:
                item = display_q.get(timeout=0.5)
            except queue.Empty:
                continue

            req_id, device_id, uri, method, data_str, full_data = item
            tag = _short_device_id(device_id)

            data, _ = _parse_request_data([data_str] if data_str else [])

            with state_lock:
                is_new = uri not in seen_uris
                if is_new:
                    seen_uris.add(uri)
                    discovered_apis.append({"uri": uri, "method": method, "data": data_str})
                request_count[0] += 1
                is_known = uri in known_urls

            path = uri.replace(BASE_URL, "")
            prefix = f"[{tag}] "

            # 终端输出
            safe_print("", Colors.RESET)

            if is_error := (full_data and "_error" in full_data):
                safe_print(f"{prefix}!! {method} {path}", Colors.RED, bold=True)
            elif is_new:
                safe_print(f"{prefix}>> {method} {path} [NEW]", Colors.GREEN, bold=True)
            else:
                safe_print(f"{prefix}>> {method} {path}", Colors.BLUE)

            if data and data != {"raw": ""}:
                data_display = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)
                safe_print(f"{prefix}   请求: {data_display}", Colors.DIM)

            # 只展示完整解析的响应
            if full_data:
                if "_error" in full_data:
                    safe_print(f"{prefix}   响应: (requests调用失败: {full_data['_error']})", Colors.RED)
                else:
                    resp_display = json.dumps(full_data, ensure_ascii=False, indent=2)
                    safe_print(f"{prefix}   响应 [完整]:\n{resp_display}", Colors.WHITE)
            elif is_error:
                safe_print(f"{prefix}   响应: (异常/无响应)", Colors.RED)
            else:
                safe_print(f"{prefix}   响应: (等待解析...)", Colors.DIM)

            # 存入记忆库
            if not is_known:
                added = _memory_mgr.add(uri, method, data_str)
                if added:
                    safe_print(f"  [{tag}]  已存入记忆库: {method} {path}", Colors.DIM)

            # HTML 模式：存入日志缓冲区
            if html_mode:
                log_entry = {
                    'id': next_log_id(),
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'device': tag,
                    'method': method,
                    'path': path,
                    'is_new': is_new,
                    'is_error': is_error,
                    'request_data': json.dumps(data, ensure_ascii=False, indent=2) if data and data != {"raw": ""} else None,
                    'response_data': json.dumps(full_data, ensure_ascii=False, indent=2) if full_data and "_error" not in full_data else None,
                }
                log_buffer.add(log_entry)

            display_q.task_done()

    def process_line(content, device_id, buf):
        """处理 logcat 行"""
        enqueued = False

        if "*** Request ***" in content:
            if buf["uri"] and buf["method"]:
                req_id = buf["seq"]
                request_q.put((req_id, device_id, buf["uri"], buf["method"], " ".join(buf["data_lines"])))
                enqueued = True
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

        elif "*** Response ***" in content:
            buf["in_response"] = "headers"
            buf["response_lines"] = []
            return enqueued

        elif "*** DioException ***" in content:
            if buf["uri"] and buf["method"]:
                req_id = buf["seq"]
                request_q.put((req_id, device_id, buf["uri"], buf["method"], " ".join(buf["data_lines"])))
                enqueued = True
            buf["uri"] = None
            buf["in_response"] = False
            return enqueued

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

        elif "uri:" in content and "https://" in content:
            m = re.search(r'uri:\s*(https?://\S+)', content)
            if m:
                buf["uri"] = m.group(1).strip()
                path = buf["uri"].replace(BASE_URL, "")
                if any(h in path for h in hide_list):
                    buf["uri"] = None
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
        """logcat 读取线程"""
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
            if buf["uri"] and buf["method"]:
                request_q.put((buf["seq"], device_id, buf["uri"], buf["method"], " ".join(buf["data_lines"])))
            if proc:
                proc.terminate()

    # 启动线程前，清空 logcat 缓冲区（避免旧日志刷屏）
    for device_id in devices:
        tag = _short_device_id(device_id)
        try:
            subprocess.run(["adb", "-s", device_id, "logcat", "-c"],
                           capture_output=True, timeout=5)
            safe_print(f"  [{tag}] 已清空 logcat 缓冲区", Colors.DIM)
        except Exception:
            pass

    logcat_threads = []
    for device_id in devices:
        t = threading.Thread(target=logcat_reader, args=(device_id,), daemon=True)
        t.start()
        logcat_threads.append(t)

    worker_threads = []
    if full_mode:
        http_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="http-worker")
        for _ in range(4):
            ft = http_pool.submit(http_worker)
            worker_threads.append(ft)

    display_thread = threading.Thread(target=display_worker, daemon=True)
    display_thread.start()

    # 主线程等待
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

        try:
            request_q.join(timeout=5)
        except Exception:
            pass

        if full_mode:
            http_pool.shutdown(wait=False)

        try:
            display_q.join(timeout=5)
        except Exception:
            pass

        _memory_mgr.shutdown()

        if html_mode:
            try:
                html_server.shutdown()
            except Exception:
                pass

        new_count = len(seen_uris) - len(known_urls)
        cprint(f"\n已停止，共捕获 {request_count[0]} 个请求，发现 {new_count} 个新接口", Colors.DIM)

        if discovered_apis:
            cprint("\n发现的接口列表:", Colors.YELLOW, bold=True)
            for api in discovered_apis:
                cprint(f"  {api['method']} {api['uri'].replace(BASE_URL, '')}", Colors.WHITE)


# ============== CLI ==============

def main():
    parser = argparse.ArgumentParser(
        description="斯诺克大师 App API 抓包调试工具 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python api_tool.py log                    # 实时查看日志
  python api_tool.py extract app_log.txt    # 从日志文件提取接口
  python api_tool.py call user              # 调用用户信息接口
  python api_tool.py auto                   # 实时监控 + 自动发现
  python api_tool.py auto --full            # 异步获取完整响应
  python api_tool.py auto --full --html     # 异步 + HTML 实时查看（浏览器访问 http://localhost:8765）
  python api_tool.py auto --full --html --port 9000  # 指定 HTML 端口
  python api_tool.py list                   # 列出所有已知接口
        """
    )

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

    auto_parser = subparsers.add_parser("auto", help="实时监控 + 自动发现接口")
    auto_parser.add_argument("-s", "--device", nargs="+", default=None, help="指定 ADB 设备 ID")
    auto_parser.add_argument("--hide", nargs="+", default=[
        "/mobile/getUserBoxStatus",
        "/mp/user/info",
        "/mp/rank/clubList",
        "/mp/record/deviceOnlineInfo",
        "/mp/record/opponentStatistics",
        "/mp/coupon/checkEligibility",
    ], help="隐藏高频轮询接口（默认隐藏6个后台轮询接口）")
    auto_parser.add_argument("--full", action="store_true", help="异步获取完整响应")
    auto_parser.add_argument("--html", action="store_true", help="启动 HTML 实时查看")
    auto_parser.add_argument("--port", type=int, default=8765, help="HTML 服务端口 (默认 8765)")

    list_parser = subparsers.add_parser("list", help="列出所有已知接口")

    args = parser.parse_args()

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
