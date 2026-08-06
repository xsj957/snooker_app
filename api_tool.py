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
"""

import argparse
import subprocess
import re
import json
import sys
import os
import time
import requests
from datetime import datetime
from collections import OrderedDict

# ============== 配置 ==============

BASE_URL = "https://test.supervisions.cn"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjanNqIiwiaXNzIjoiY2pzaiIsImV4cCI6MTgxNzQ2NzY1MywiYXV0aFR5cGUiOjQsInVzZXJJZCI6IjU3ZDcwM2RjLTY1OWEtNDQ3NC04OThlLWI3NWVmYTFmMmUwYSJ9.evzNsb2k7yv33yNU8BDsit7FCN-eNCQk5iD5YL12h2c",
    "refresh_token": "ecbe9fe8a12e045be53db01e88f81da2"
}

USER_ID = "57d703dc-659a-4474-898e-b75efa1f2e0a"

ADB_DEVICE = "10AECL22YX0023T"

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
    pattern = args.pattern or "DIO"
    adb_cmd = ["adb", "-s", ADB_DEVICE, "logcat"]

    cprint(f"实时日志流 | 过滤: {pattern} | Ctrl+C 停止", Colors.CYAN, bold=True)
    cprint("=" * 60)

    try:
        proc = subprocess.Popen(
            adb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1
        )

        import io
        stdout_reader = io.TextIOWrapper(proc.stdout, encoding='utf-8', errors='replace')

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

    # 预定义的快捷接口
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
        "trial": {
            "name": "试用券列表",
            "method": "POST",
            "url": f"{BASE_URL}/mp/coupon/trialList",
            "data": {"pageNo": 1, "pageSize": 100, "status": 0, "userId": USER_ID}
        },
        "matches": {
            "name": "对手列表和视频",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/opponentListWithVideos",
            "data": {"startTime": "2020-01-01 00:00:00", "endTime": "2030-12-31 23:59:59", "page": 1, "pageSize": 100, "userId": USER_ID}
        },
        "stats": {
            "name": "对手统计数据",
            "method": "POST",
            "url": f"{BASE_URL}/mp/record/opponentStatistics",
            "data": {"startTime": "2020-01-01 00:00:00", "endTime": "2030-12-31 23:59:59", "userId": USER_ID}
        },
        "track": {
            "name": "埋点上报",
            "method": "POST",
            "url": f"{BASE_URL}/mp/event/track",
            "data": {"modelType": 1, "eventType": 1, "attrName": "launch_source", "attrValue": "cold", "clientType": 1, "userId": USER_ID}
        }
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
            timeout=10
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
        "box": "POST /mobile/getUserBoxStatus - 获取盒子状态",
        "version": "POST /mp/app/version/check - 检查版本",
        "coupon": "POST /mp/coupon/checkEligibility - 检查视频券",
        "trial": "POST /mp/coupon/trialList - 试用券列表",
        "matches": "POST /mp/record/opponentListWithVideos - 对手列表和视频",
        "stats": "POST /mp/record/opponentStatistics - 对手统计",
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

def _display_request_response(uri, method, data_lines, response_lines, seen_uris, discovered_apis, is_error=False):
    """显示一个完整的请求+响应"""
    # 解析 data
    data_str = " ".join(data_lines)
    data = None
    try:
        data = json.loads(data_str)
    except:
        data = _dart_to_json(data_str)
    if data is None:
        data = {"raw": data_str[:200]}

    # 解析响应
    response_text = " ".join(response_lines).strip()
    response_data = None
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

    print()  # 空行分隔
    if is_error:
        cprint(f"!! {method} {path}{marker}", Colors.RED, bold=True)
    elif is_new:
        cprint(f">> {method} {path}{marker}", Colors.GREEN, bold=True)
    else:
        cprint(f">> {method} {path}", Colors.BLUE)

    # 请求参数
    if data and data != {"raw": ""}:
        data_display = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)
        cprint(f"   请求: {data_display}", Colors.DIM)

    # 响应体
    if response_data:
        resp_display = json.dumps(response_data, ensure_ascii=False, indent=2)
        # 截断过长响应
        if len(resp_display) > 1500:
            resp_display = resp_display[:1500] + "\n   ... (已截断)"
        cprint(f"   响应:\n{resp_display}", Colors.WHITE)
    elif response_text:
        cprint(f"   响应: {response_text[:500]}", Colors.WHITE)
    elif is_error:
        cprint(f"   响应: (异常/无响应)", Colors.RED)
    else:
        cprint(f"   响应: (等待中...)", Colors.DIM)


def cmd_auto(args):
    """实时监控 + 自动发现新接口"""
    cprint("自动监控模式 | 实时发现新接口并获取完整响应", Colors.CYAN, bold=True)
    hide_list = getattr(args, 'hide', []) or []
    if hide_list:
        cprint(f"已隐藏接口: {', '.join(hide_list)}", Colors.DIM)
    cprint("Ctrl+C 停止", Colors.DIM)
    cprint("=" * 60)

    seen_uris = set()
    discovered_apis = []  # 记录所有发现的接口

    adb_cmd = ["adb", "-s", ADB_DEVICE, "logcat"]

    try:
        proc = subprocess.Popen(
            adb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1
        )

        import io
        stdout_reader = io.TextIOWrapper(proc.stdout, encoding='utf-8', errors='replace')

        # 当前请求缓冲区
        current_uri = None
        current_method = None
        current_data_lines = []
        current_auth = None
        current_refresh = None
        current_response_lines = []
        in_data = False
        in_response = False
        request_count = 0

        for line in stdout_reader:
            content = line.strip()

            if "*** Request ***" in content:
                # 显示上一个请求的响应（如果有）
                if current_uri:
                    path = current_uri.replace(BASE_URL, "")
                    should_hide = any(h in path for h in hide_list)
                    if not should_hide:
                        is_new = current_uri not in seen_uris
                        _display_request_response(
                            current_uri, current_method, current_data_lines,
                            current_response_lines, seen_uris, discovered_apis
                        )
                        # 自动存入记忆库
                        if is_new:
                            added = add_to_memory(
                                current_uri, current_method,
                                " ".join(current_data_lines)
                            )
                            if added:
                                cprint(f"  💾 已存入记忆库: {current_method} {current_uri.replace(BASE_URL, '')}", Colors.DIM)
                    else:
                        # 隐藏但仍记录为新接口
                        if current_uri not in seen_uris:
                            seen_uris.add(current_uri)
                            discovered_apis.append({
                                "uri": current_uri,
                                "method": current_method,
                                "data": " ".join(current_data_lines)
                            })
                            add_to_memory(current_uri, current_method, " ".join(current_data_lines))
                    request_count += 1

                # 重置
                current_uri = None
                current_method = None
                current_data_lines = []
                current_auth = None
                current_refresh = None
                current_response_lines = []
                in_data = False
                in_response = False

            elif "*** Response ***" in content:
                in_response = "headers"  # 先跳过 headers
                current_response_lines = []

            elif "*** DioException ***" in content:
                # 异常也结束响应收集
                if current_uri:
                    path = current_uri.replace(BASE_URL, "")
                    should_hide = any(h in path for h in hide_list)
                    if not should_hide:
                        _display_request_response(
                            current_uri, current_method, current_data_lines,
                            current_response_lines, seen_uris, discovered_apis,
                            is_error=True
                        )
                    request_count += 1
                current_uri = None
                in_response = False

            elif in_response == "headers" and "Response Text:" in content:
                in_response = "body"  # 开始收集响应正文
                # Response Text: 和响应 JSON 可能在同一行
                after_marker = content.split("Response Text:")[-1].strip()
                if after_marker and "[DIO]" not in after_marker:
                    current_response_lines.append(after_marker)
            elif in_response == "body" and content:
                # 只收集 [DIO] 开头的行，遇到非 DIO 行就停止
                if "[DIO]" in content:
                    after_dio = content.split("[DIO]")[-1].strip()
                    if after_dio and not after_dio.startswith("***"):
                        current_response_lines.append(after_dio)
                else:
                    in_response = False  # 非 DIO 行，结束收集

            elif "uri:" in content and "https://" in content:
                m = re.search(r'uri:\s*(https?://\S+)', content)
                if m:
                    current_uri = m.group(1).strip()

            elif "method:" in content:
                m = re.search(r'method:\s*(\w+)', content)
                if m:
                    current_method = m.group(1).strip()

            elif "Authorization:" in content:
                m = re.search(r'Authorization:\s*(\S+)', content)
                if m:
                    current_auth = m.group(1).strip()

            elif "refresh_token:" in content:
                m = re.search(r'refresh_token:\s*(\S+)', content)
                if m:
                    current_refresh = m.group(1).strip()

            elif "data:" in content:
                in_data = True
                current_data_lines = []
                after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
                if "{" in after_dio and after_dio != "data:":
                    current_data_lines.append(after_dio.replace("data:", "").strip())

            elif in_data:
                after_dio = content.split("[DIO]")[-1].strip() if "[DIO]" in content else content.strip()
                if "*** " in after_dio or after_dio == "":
                    in_data = False
                elif after_dio and ("{" in after_dio or after_dio.startswith('"') or ":" in after_dio):
                    current_data_lines.append(after_dio)

    except KeyboardInterrupt:
        # 显示最后一个请求
        if current_uri:
            path = current_uri.replace(BASE_URL, "")
            should_hide = any(h in path for h in hide_list)
            if not should_hide:
                _display_request_response(
                    current_uri, current_method, current_data_lines,
                    current_response_lines, seen_uris, discovered_apis
                )
            request_count += 1
        cprint(f"\n已停止，共捕获 {request_count} 个请求，发现 {len(seen_uris)} 个新接口", Colors.DIM)
        if discovered_apis:
            cprint("\n发现的接口列表:", Colors.YELLOW, bold=True)
            for api in discovered_apis:
                cprint(f"  {api['method']} {api['uri'].replace(BASE_URL, '')}", Colors.WHITE)
            cprint(f"\n提示: 将新接口添加到 api_tool.py 的 presets 中即可用 call 命令调用", Colors.DIM)
    finally:
        proc.terminate()


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
        resp = requests.post(uri, json=data, headers=HEADERS, timeout=10)
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
  python api_tool.py list                   # 列出所有已知接口
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # log
    log_parser = subparsers.add_parser("log", help="实时查看 App 网络日志")
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
    auto_parser.add_argument("--hide", nargs="+", default=[
        "/mobile/getUserBoxStatus",
        "/mp/user/info",
    ], help="隐藏高频轮询接口路径 (默认隐藏 getUserBoxStatus 和 user/info)")

    # list
    list_parser = subparsers.add_parser("list", help="列出所有已知接口")

    args = parser.parse_args()

    if args.command == "log":
        cmd_log(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "call":
        cmd_call(args)
    elif args.command == "auto":
        cmd_auto(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
