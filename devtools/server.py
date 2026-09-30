#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevTools 后端服务 — 抓包核心 + HTTP 服务 + HTML 托管
"""

import os
import re
import json
import time
import math
import base64
import gzip
import threading
import urllib.parse
import http.client
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============== 配置（由 configure() 或 logcat 自动检测动态注入） ==============

BASE_URL = "https://test.supervisions.cn"

# 环境域名映射
ENV_DOMAINS = {
    "test.supervisions.cn": "test",
    "app.supervisions.cn": "prod",
}
ENV_LABELS = {"test": "测试", "prod": "生产"}

# API 中文注释表（路径 → 中文名）
API_DESC = {
    # 用户
    "/mp/user/info": "用户信息",
    "/mp/user/myClubs": "我的俱乐部",
    "/mp/user/saveDefaultClub": "设置默认俱乐部",
    "/mp/user/rating": "我的评级",
    "/mp/user/breakScoreList": "单杆分列表",
    "/mp/user/deleteAccount": "注销账号",
    # 登录
    "/mp/oauth/wechatLogin": "微信登录",
    # 版本
    "/mp/app/version/check": "版本检查",
    "/mp/app/domestic/version/check": "国内版版本检查",
    # 视频券
    "/mp/coupon/checkEligibility": "视频券资格检查",
    "/mp/coupon/trialList": "体验券列表",
    "/mp/coupon/queryCouponList": "我的视频券",
    # 交手记录
    "/mp/record/opponentListWithVideos": "交手卡片列表",
    "/mp/record/opponentStatistics": "对手统计",
    "/mp/record/competitionListWithVideos": "比赛场次列表",
    "/mp/record/competitionStatistics": "交手统计(双人)",
    "/mp/record/inningList": "局列表",
    "/mp/record/inningStatistics": "场次统计",
    "/mp/record/markVideoViewed": "标记视频已观看",
    "/mp/record/deviceOnlineInfo": "设备在线信息",
    "/mp/record/barchart": "柱状图数据",
    "/mp/record/statics": "个人统计数据",
    # 排行
    "/mp/rank/clubList": "俱乐部排行",
    "/mp/rank/userBreakRank": "单杆排行",
    "/mp/rank/ratingList": "评级排行",
    "/mp/rank/breakList": "进球排行",
    "/mp/rank/winRateList": "胜率排行",
    # 埋点
    "/mp/event/track": "埋点上报",
    "/mp/video/addVideoEventFromMobile": "App播放事件上报",
    # 盒子/工控机
    "/mobile/getUserBoxStatus": "盒子状态",
    "/mobile/loginBoxAfterScanningQrCode": "扫码登录盒子",
    # 我的视频
    "/video/videoClient/getVideoStatistics": "视频统计概览",
    "/video/videoClient/myVideos/processingV2": "制作中视频",
    "/video/videoClient/myVideos/readyV2": "有效视频列表",
    "/video/videoClient/myVideos/failedV2": "失效视频列表",
    "/video/videoClient/updateClientInfo": "更新设备信息",
    "/video/videoClient/updateStatus": "更新视频状态",
    # 视频详情/解锁
    "/video/videoinfo/competitionVideos": "比赛场详情",
    "/video/videoinfo/buyitUseComboV3": "视频券解锁",
    # 退款
    "/video/videoOrder/appPostVideoRefund": "视频退款",
}


def detect_env(uri):
    """从 URL 检测环境（test/prod）"""
    try:
        parsed = urllib.parse.urlparse(uri)
        host = parsed.hostname or ""
        return ENV_DOMAINS.get(host, "unknown")
    except Exception:
        return "unknown"


def extract_path(uri):
    """从 URL 提取纯路径（不含域名），兼容测试/生产环境"""
    try:
        parsed = urllib.parse.urlparse(uri)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return path
    except Exception:
        return uri


def get_env_label(env):
    """获取环境中文标签"""
    return ENV_LABELS.get(env, "未知")

# ============== logcat 系统行识别 ==============

# 完整 logcat 行头: 日期 时间 PID TID 级别 (如 "09-28 14:33:22.006 18894 18960 D SurfaceComposerClient: ")
# Dio 协议行带 [DIO] 标记、多行消息续行无任何行头，因此本正则只命中真正的系统日志行
SYS_LOG_LINE_RE = re.compile(r'^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s')
# 无锚定版: 污染检测用（污染串中系统行头出现在行中，以空格/无分隔拼接）
SYS_LOG_SIG_RE = re.compile(r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEF]\s')
# 行头时间戳（capture 路径计算真实耗时用）
SYS_LOG_TS_RE = re.compile(r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)')


def is_sys_log_line(content):
    """是否为 logcat 系统日志行（无 [DIO] 标记且带完整行头）"""
    if not content or '[DIO]' in content:
        return False
    return bool(SYS_LOG_LINE_RE.match(content.strip()))


def is_polluted_text(text):
    """文本中是否混入了 logcat 系统行（污染签名，行中亦命中）"""
    return bool(text) and bool(SYS_LOG_SIG_RE.search(text))


# ============== 二次请求重放策略 ==============
# DENY: 有副作用接口，重放会改变服务端状态（解锁/退款/标记已看/上报/设备信息/登录），绝对禁止重放
# ALLOW: 已知纯查询接口（POST 但只读）
# 其余未知接口: 测试环境允许重放（UI 标注），生产环境禁止重放（防误操作生产数据）
# 绝对禁放: 非幂等/消耗性/破坏性操作，重放一次就多一次真实副作用
REPLAY_DENY_PATHS = {
    "/video/videoinfo/buyitUseComboV3",     # 视频券解锁/购买（真实扣券）
    "/video/videoOrder/appPostVideoRefund", # 视频退款（真实退款）
    "/mp/user/deleteAccount",               # 注销账号
    "/mp/oauth/wechatLogin",                # 登录（消耗授权码）
    "/mobile/loginBoxAfterScanningQrCode",  # 扫码登录盒子
}
# 测试环境放行 / 生产禁止: 幂等写(重发捕获体=重设同一状态)与埋点上报(测试对象);
# 生产环境重放会写脏线上数据/统计
REPLAY_TEST_ONLY_PATHS = {
    "/mp/event/track",                      # 埋点上报
    "/mp/video/addVideoEventFromMobile",    # App 播放事件上报
    "/video/videoClient/updateStatus",      # 视频状态变更（幂等写）
    "/video/videoClient/updateClientInfo",  # 设备信息写入（幂等写）
    "/mp/record/markVideoViewed",           # 标记视频已观看（幂等写）
    "/mp/record/markVideoViewedFromMobile",
    "/mp/user/saveDefaultClub",             # 默认俱乐部写入（幂等写）
}
REPLAY_ALLOW_PATHS = {
    "/mp/user/info", "/mp/user/myClubs", "/mp/user/rating", "/mp/user/breakScoreList",
    "/mp/app/version/check", "/mp/app/domestic/version/check",
    "/mp/coupon/checkEligibility", "/mp/coupon/trialList", "/mp/coupon/queryCouponList",
    "/mp/record/opponentListWithVideos", "/mp/record/opponentStatistics",
    "/mp/record/competitionListWithVideos", "/mp/record/competitionStatistics",
    "/mp/record/inningList", "/mp/record/inningStatistics",
    "/mp/record/deviceOnlineInfo", "/mp/record/barchart", "/mp/record/statics",
    "/mp/rank/clubList", "/mp/rank/userBreakRank", "/mp/rank/ratingList",
    "/mp/rank/breakList", "/mp/rank/winRateList",
    "/mobile/getUserBoxStatus",
    "/video/videoClient/getVideoStatistics", "/video/videoClient/myVideos/processingV2",
    "/video/videoClient/myVideos/readyV2", "/video/videoClient/myVideos/failedV2",
    "/video/videoinfo/competitionVideos",
}


def _norm_replay_path(path):
    """重放闸门路径归一: 去 query/尾斜杠、小写、%解码、折叠 . 与 .. —— 防变体绕过 DENY"""
    import posixpath
    p = (path or '').split('?')[0]
    try:
        p = urllib.parse.unquote(p)
    except Exception:
        pass
    p = posixpath.normpath(p.lower())
    if p in ('.', '/'):
        p = '/'
    return p


REPLAY_DENY_PATHS = {_norm_replay_path(p) for p in REPLAY_DENY_PATHS}
REPLAY_ALLOW_PATHS = {_norm_replay_path(p) for p in REPLAY_ALLOW_PATHS}
REPLAY_TEST_ONLY_PATHS = {_norm_replay_path(p) for p in REPLAY_TEST_ONLY_PATHS}


def replay_policy(path, env, no_replay=False):
    """二次请求重放闸门: 返回 (allowed, reason)"""
    if no_replay:
        return False, '--no-replay 被动模式'
    p = _norm_replay_path(path)
    if p in REPLAY_DENY_PATHS:
        return False, '副作用接口，禁止重放'
    if p in REPLAY_TEST_ONLY_PATHS:
        if env == 'test':
            return True, '埋点上报接口(测试环境放行)'
        return False, '埋点上报接口(生产环境禁重放)'
    if p in REPLAY_ALLOW_PATHS:
        return True, '已知只读接口'
    if env == 'test':
        return True, '未知接口(测试环境)'
    return False, '未知接口(生产环境防误操作)'


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
_auto_auth_lock = threading.Lock()  # 保护 _auto_auth 的并发访问

# HTML 已内嵌到 devtools/html_template.py 中，无需外部 index.html 文件


def get_html():
    """返回内嵌的 DevTools HTML 页面"""
    from devtools.html_template import DEVTOOLS_HTML
    return DEVTOOLS_HTML


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

def _parse_dart_value(s, i, scalars_as_str):
    """从 s[i] 起解析一个 Dart 字面量值，返回 (value, 下一个下标)。

    递归解析 Map/List/带引号字符串/裸标量；括号深度不会变负，
    多余的收尾字符由调用方忽略（修复旧版"负深度塌缩"缺陷）。
    scalars_as_str=True 时标量保留原文（headers 采集专用，避免 null→'None'）。
    """
    while i < len(s) and s[i] in ' \t\r\n':
        i += 1
    if i >= len(s):
        return None, i
    ch = s[i]
    if ch == '{':
        obj = {}
        i += 1
        while i < len(s):
            while i < len(s) and s[i] in ' \t\r\n,':
                i += 1
            if i >= len(s):
                break
            if s[i] == '}':
                i += 1
                break
            key_start = i
            while i < len(s) and s[i] != ':':
                i += 1
            if i >= len(s):
                break
            key = s[key_start:i].strip()
            i += 1
            val, i = _parse_dart_value(s, i, scalars_as_str)
            if key:
                obj[key] = val
        return obj, i
    if ch == '[':
        arr = []
        i += 1
        while i < len(s):
            while i < len(s) and s[i] in ' \t\r\n,':
                i += 1
            if i >= len(s):
                break
            if s[i] == ']':
                i += 1
                break
            val, i = _parse_dart_value(s, i, scalars_as_str)
            arr.append(val)
        return arr, i
    if ch in ('"', "'"):
        quote = ch
        i += 1
        buf = []
        while i < len(s):
            c = s[i]
            if c == '\\' and i + 1 < len(s):
                buf.append(s[i + 1])
                i += 2
                continue
            if c == quote:
                i += 1
                break
            buf.append(c)
            i += 1
        return ''.join(buf), i
    # 裸标量: 读到顶层逗号或收尾括号为止
    # scalars_as_str(headers 采集)模式下, 逗号后不像"key:"时视为值内逗号(如 Accept: a,b)
    start = i
    depth = 0
    while i < len(s):
        c = s[i]
        if c in '{[':
            depth += 1
        elif c in '}]':
            if depth == 0:
                break
            depth -= 1
        elif c == ',' and depth == 0:
            if scalars_as_str and not re.match(r'\s*[\w\-\.]+\s*:', s[i + 1:]):
                i += 1
                continue
            break
        i += 1
    raw = s[start:i].strip()
    if scalars_as_str:
        return raw, i
    if raw == 'null':
        return None, i
    if raw == 'true':
        return True, i
    if raw == 'false':
        return False, i
    try:
        return int(raw), i
    except ValueError:
        pass
    try:
        return float(raw), i
    except ValueError:
        pass
    return raw, i


def _dart_to_json(dart_str, scalars_as_str=False):
    """将 Dart 风格字面量（Map/List toString 打印）转为 JSON 兼容结构。

    v3.2 重写: 递归解析、支持嵌套 Map/List 与方括号；深度不为负；
    输入不以 { 或 [ 开头时返回 None。
    """
    if not dart_str:
        return None
    s = dart_str.strip()
    if not s or s[0] not in '{[':
        return None
    value, _ = _parse_dart_value(s, 0, scalars_as_str)
    return value


def _brackets_balanced(text):
    """括号配平校验: 引号感知 + {} [] 分别配对（引号内括号不计，错配即 False）"""
    stack = []
    in_str = None
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in '"\'':
            in_str = ch
        elif ch in '{[':
            stack.append(ch)
        elif ch in '}]':
            if not stack or stack[-1] != ('{' if ch == '}' else '['):
                return False
            stack.pop()
    return not stack and in_str is None


def _dart_parse_complete(text):
    """Dart 字面量是否可解析且被完全消费（带尾巴的截断/污染串判 False）"""
    if not text or text[0] not in '{[':
        return False
    val, i = _parse_dart_value(text, 0, False)
    return val is not None and text[i:].strip() == ''


def _parse_request_data(data_str):
    """解析请求数据，返回 (data, raw_str, parse_ok)。

    parse_ok=False 表示原文既非合法 JSON 也非可解析 Dart 字面量，
    调用方应展示原文并拒绝据此重放（不再伪造 {"raw": ...} 对象）。
    """
    data_str = "".join(data_str).strip() if isinstance(data_str, (list, tuple)) else (data_str or '').strip()
    if not data_str:
        return {}, data_str, True
    try:
        return json.loads(data_str), data_str, True
    except (json.JSONDecodeError, ValueError):
        pass
    parsed = _dart_to_json(data_str)
    if isinstance(parsed, (dict, list)):
        return parsed, data_str, True
    return {}, data_str, False


def _fetch_error(reason):
    return {
        'status': 0, 'headers': {}, 'body': None, 'raw_text': None,
        'size': 0, 'time_ms': 0, 'timing': {}, 'redirects': 0,
        'body_note': None, 'error': reason,
    }


def _fetch_full_response(uri, method, data_str, req_headers=None):
    """重放 App 原始请求，获取完整响应（status/headers/size/timing/raw_text）

    v3.2 保真约定（目标: 重放请求 == 抓包请求，响应才有可比性）:
    - body 按捕获原文重建: 仅当 JSON 合法、或 Dart 字面量可解析且括号配平时才发送，
      以 ensure_ascii=False 紧凑格式序列化（贴近 Dio jsonEncode 字节）;
      污染/不配平/不可解析的 body 一律拒绝重放（error=body_*），绝不伪造 {"raw":...} 发出;
    - headers 以捕获原始头为基准（键名大小写不敏感合并），全局 HEADERS 只补缺失;
      剔除 Dio 元数据字段与 accept-encoding（避免收到无法解压的 gzip 体）;
    - 手动跟随 3xx 重定向最多 5 次（对齐 Dio followRedirects 默认行为）;
    - 按响应头 charset 解码; raw_text 保留完整原文供 Raw 页签与一致性比对。
    """
    upper_method = (method or 'GET').upper()

    # ---- body 重建: 宁可拒发，不可错发 ----
    body_bytes = None
    body_note = None
    if upper_method not in ("GET", "HEAD") and data_str:
        if is_polluted_text(data_str):
            return _fetch_error('body_polluted: 请求体混入 logcat 系统行，拒绝重放')
        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            data = _dart_to_json(data_str)
            if data is None or not _brackets_balanced(data_str) or not _dart_parse_complete(data_str):
                return _fetch_error('body_unparseable: 请求体不完整/不可解析/带尾巴，拒绝重放')
            body_note = 'body 由 Dart 字面量重建'
        body_bytes = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

    # ---- headers: 仅用捕获原始头（大小写不敏感）----
    # v3.2: 不再注入全局 HEADERS 的 Authorization —— 重放请求必须 == 抓包请求，
    # 公开接口/未捕获到头的请求若被注入 token，服务端可能返回与抓包不同的数据
    DIO_META = {"contenttype", "content-length", "followredirects", "responsetype", "accept-encoding"}
    hdr_map = {}  # lower -> (原始键名, 值)
    if req_headers:
        for k, v in req_headers.items():
            kl = k.lower()
            if kl in DIO_META:
                continue
            hdr_map[kl] = (k, str(v))
    if upper_method in ("GET", "HEAD"):
        hdr_map.pop('content-type', None)
        hdr_map.pop('content-length', None)
    elif body_bytes is not None:
        if 'content-type' not in hdr_map:
            hdr_map['content-type'] = ('Content-Type', 'application/json')
        hdr_map['content-length'] = ('Content-Length', str(len(body_bytes)))
    send_headers = {k: v for (k, v) in hdr_map.values()}

    # ---- 发送 + 重定向跟随 ----
    conn = None
    target = uri
    redirects = 0
    m_now, bb_now = upper_method, body_bytes
    try:
        t_start = time.time()
        while True:
            parsed = urllib.parse.urlparse(target)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            if parsed.scheme == 'https':
                conn = http.client.HTTPSConnection(host, port, timeout=15)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=15)
            conn.request(m_now, path, body=bb_now, headers=send_headers)
            resp = conn.getresponse()
            t_first_byte = time.time()
            resp_body_raw = resp.read()
            t_end = time.time()
            if resp.status in (301, 302, 303, 307, 308) and redirects < 5:
                loc = resp.getheader('Location')
                if loc:
                    redirects += 1
                    target = urllib.parse.urljoin(target, loc)
                    if resp.status == 303:
                        m_now, bb_now = 'GET', None
                    conn.close()
                    conn = None
                    continue
            break

        ttfb_ms = round((t_first_byte - t_start) * 1000, 1)
        download_ms = round((t_end - t_first_byte) * 1000, 1)
        total_ms = round((t_end - t_start) * 1000, 1)

        if (resp.getheader('Content-Encoding') or '').lower() == 'gzip':
            try:
                resp_body_raw = gzip.decompress(resp_body_raw)
            except Exception:
                pass
        ctype = resp.getheader('Content-Type') or ''
        cm = re.search(r'charset=([\w\-]+)', ctype, re.I)
        enc = cm.group(1) if cm else 'utf-8'
        try:
            raw_text = resp_body_raw.decode(enc, errors='replace')
        except (LookupError, TypeError):
            raw_text = resp_body_raw.decode('utf-8', errors='replace')

        body = None
        try:
            body = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError):
            body = raw_text

        return {
            'status': resp.status,
            'headers': dict(resp.getheaders()),
            'body': body,
            'raw_text': raw_text,
            'size': len(resp_body_raw),
            'time_ms': total_ms,
            'timing': {'ttfb': ttfb_ms, 'download': download_ms},
            'redirects': redirects,
            'body_note': body_note,
            'error': None
        }
    except Exception as e:
        return _fetch_error(str(e))
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============== API 记忆库 ==============

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_memory.json")


class MemoryManager:
    """线程安全的 API 记忆库管理器"""

    # 条目过期时间（秒）。默认 30 天
    MAX_AGE_SECONDS = 30 * 24 * 3600

    def __init__(self, filepath):
        self._filepath = filepath
        self._lock = threading.Lock()          # 保护 self._cache（内存）
        self._disk_lock = threading.Lock()     # 保护文件写入（磁盘），与 _lock 分离避免 Windows PermissionError
        self._cache = self._load()
        self._purge_expired()
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

    def _purge_expired(self):
        """清理超过 MAX_AGE_SECONDS 的旧条目"""
        cutoff = datetime.now().timestamp() - self.MAX_AGE_SECONDS
        to_remove = []
        for key, val in self._cache.items():
            discovered = val.get("discovered_at", "")
            try:
                dt = datetime.strptime(discovered, "%Y-%m-%d %H:%M:%S")
                if dt.timestamp() < cutoff:
                    to_remove.append(key)
            except (ValueError, TypeError):
                pass
        for key in to_remove:
            del self._cache[key]
        if to_remove:
            self._dirty = True

    def _save_to_disk(self):
        """写磁盘 — 原子写入：先写临时文件，再 rename，防止崩溃导致数据丢失"""
        with self._disk_lock:
            try:
                # 在 disk_lock 内快照 cache，保证写入一致性
                snapshot = dict(self._cache)
                tmp_path = self._filepath + '.tmp'
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
                # 原子替换（Windows 上 rename 会覆盖已存在的目标文件）
                if os.path.exists(self._filepath):
                    os.replace(tmp_path, self._filepath)
                else:
                    os.rename(tmp_path, self._filepath)
                self._dirty = False
            except OSError:
                pass

    def _periodic_save(self):
        try:
            should_save = False
            with self._lock:
                if self._dirty:
                    should_save = True
            if should_save:
                self._save_to_disk()
        except Exception:
            pass
        try:
            self._save_timer = threading.Timer(30.0, self._periodic_save)
            self._save_timer.daemon = True
            self._save_timer.start()
        except RuntimeError:
            pass

    def flush(self):
        should_save = False
        with self._lock:
            if self._dirty:
                should_save = True
        if should_save:
            self._save_to_disk()

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
        path = extract_path(uri)
        env = detect_env(uri)
        env_label = get_env_label(env)
        return f"{method} [{env_label}] {path}"

    def add(self, uri, method, data_str, description=""):
        # 跳过 CDN 视频原片（.mp4），不写入记忆库
        if re.search(r'\.mp4(\?|$)', uri):
            return False
        path = extract_path(uri)
        env = detect_env(uri)
        env_label = get_env_label(env)
        key = f"{method} [{env_label}] {path}"
        should_save = False
        # v3.2: 污染体（混入 logcat 系统行）永不写库
        if is_polluted_text(data_str):
            return False
        with self._lock:
            existing = self._cache.get(key)
            if existing is not None:
                # 旧条目已被污染时允许用干净抓包覆盖（修复"脏模板永久留存"）
                old_data = json.dumps(existing.get("data"), ensure_ascii=False)
                if not is_polluted_text(old_data):
                    return False
            data = None
            try:
                data = json.loads(data_str)
            except (json.JSONDecodeError, ValueError):
                data = _dart_to_json(data_str)
            # 自动填充中文描述
            if not description:
                description = API_DESC.get(path, "")
            self._cache[key] = {
                "url": uri,
                "method": method,
                "path": path,
                "env": env,
                "data": data,
                "description": description,
                "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._dirty = True
            should_save = True
        # 在锁外写磁盘，不阻塞并发读
        if should_save:
            self._save_to_disk()
        return True

    def known_urls(self):
        with self._lock:
            return {api["url"] for api in self._cache.values()}


_memory_mgr = MemoryManager(MEMORY_FILE)


# ============== 接口历史画像（混合分级重放决策） ==============

PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_profile.json")


def profile_key(uri, method):
    """画像键: 与记忆库同风格，path 不含 query（轮询参数不拆散画像）"""
    path = extract_path(uri).split('?')[0]
    env_label = get_env_label(detect_env(uri))
    return f"{method} [{env_label}] {path}"


class ProfileManager:
    """线程安全的接口历史画像: 响应尺寸分布/截断率/重放次数。

    驱动混合分级重放决策（方案 C）:
      small    = 历史最大响应 < 3500B 且截断率≤20%  → 捕获完整时零重放
      large    = 历史最大响应 ≥ 3500B               → 捕获完整也主动重放(实测元数据+DIFF)
      unstable = 截断率 > 20%（即使小也常丢块）      → 同 large 主动重放兜底
    """

    LARGE_THRESHOLD = 3500   # logcat 单条载荷上限 4076B，留余量
    UNSTABLE_RATE = 0.2
    MAX_SIZES = 100          # 保留最近 100 个尺寸样本算 p95
    MAX_AGE_SECONDS = 30 * 24 * 3600

    def __init__(self, filepath):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._disk_lock = threading.Lock()
        self._cache = self._load()
        self._purge_expired()
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

    def _purge_expired(self):
        cutoff = datetime.now().timestamp() - self.MAX_AGE_SECONDS
        for key in [k for k, v in self._cache.items()
                    if self._ts(v.get("updated_at", "")) < cutoff]:
            del self._cache[key]

    @staticmethod
    def _ts(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
        except (ValueError, TypeError):
            return 0

    def _save_to_disk(self):
        with self._disk_lock:
            try:
                snapshot = dict(self._cache)
                tmp_path = self._filepath + '.tmp'
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
                if os.path.exists(self._filepath):
                    os.replace(tmp_path, self._filepath)
                else:
                    os.rename(tmp_path, self._filepath)
                self._dirty = False
            except OSError:
                pass

    def _periodic_save(self):
        try:
            with self._lock:
                should_save = self._dirty
            if should_save:
                self._save_to_disk()
        except Exception:
            pass
        try:
            self._save_timer = threading.Timer(30.0, self._periodic_save)
            self._save_timer.daemon = True
            self._save_timer.start()
        except Exception:
            pass

    def flush(self):
        with self._lock:
            should_save = self._dirty
        if should_save:
            self._save_to_disk()

    def shutdown(self):
        try:
            self._save_timer.cancel()
        except Exception:
            pass
        self.flush()

    @classmethod
    def _classify(cls, p):
        if p["samples"] and p["trunc_count"] / p["samples"] > cls.UNSTABLE_RATE:
            return "unstable"
        if p["size_max"] >= cls.LARGE_THRESHOLD:
            return "large"
        return "small"

    @staticmethod
    def _p95(sizes):
        if not sizes:
            return 0
        s = sorted(sizes)
        return s[max(0, int(round(0.95 * (len(s) - 1))))]

    def observe(self, key, size, truncated=False, replayed=False):
        """每条展示记录回写: 展示体字节数 / 捕获是否截断 / 是否走了重放"""
        with self._lock:
            p = self._cache.get(key)
            if p is None:
                p = {"sizes": [], "size_max": 0, "samples": 0,
                     "trunc_count": 0, "replay_count": 0}
                self._cache[key] = p
            p["samples"] += 1
            p["sizes"].append(int(size))
            if len(p["sizes"]) > self.MAX_SIZES:
                p["sizes"] = p["sizes"][-self.MAX_SIZES:]
            if int(size) > p["size_max"]:
                p["size_max"] = int(size)
            if truncated:
                p["trunc_count"] += 1
            if replayed:
                p["replay_count"] += 1
            p["class"] = self._classify(p)
            p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._dirty = True

    def get(self, key):
        """返回画像副本(含 size_p95/class)，无画像返回 None"""
        with self._lock:
            p = self._cache.get(key)
            if not p:
                return None
            out = dict(p)
            out["size_p95"] = self._p95(p["sizes"])
            return out


_profile_mgr = ProfileManager(PROFILE_FILE)


# ============== 日志缓冲区 ==============

class LogBuffer:
    """线程安全的日志缓冲区，供 HTML DevTools 界面读取"""

    def __init__(self, max_size=1000):
        self._lock = threading.Lock()
        self._logs = []
        self._max_size = max_size

    def add(self, log_entry):
        with self._lock:
            # 入库前清洗一次，serve 时直接用 json.dumps（不重复清洗）
            cleaned = _clean_for_json(log_entry)
            self._logs.append(cleaned)
            if len(self._logs) > self._max_size:
                self._logs = self._logs[-self._max_size:]

    def get_all(self, since_id=None, method_filter=None, status_filter=None):
        with self._lock:
            logs = list(self._logs)

        full_reset = False
        if since_id is not None:
            found = False
            for i, log in enumerate(logs):
                if log['id'] == since_id:
                    logs = logs[i + 1:]
                    found = True
                    break
            if not found:
                # since_id 已被淘汰（buffer 溢出截断），返回全部数据让前端重建状态
                logs = list(self._logs)
                full_reset = True

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

        return logs, full_reset

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

    def reset(self):
        """启动时重置缓冲区，确保不残留上次运行的数据"""
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


def _clean_for_json(o):
    """递归清理字符串中的孤立 surrogate 与非有限浮点，确保 json.dumps + utf-8 编码不报错。
    在数据入库时调用一次，避免每次轮询重复清洗。"""
    if isinstance(o, str):
        return o.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    elif isinstance(o, float):
        # NaN/Infinity 不是合法 JSON，浏览器 JSON.parse 会整页抛错 → 转字符串保留信息
        return o if math.isfinite(o) else str(o)
    elif isinstance(o, list):
        return [_clean_for_json(item) for item in o]
    elif isinstance(o, dict):
        return {_clean_for_json(k): _clean_for_json(v) for k, v in o.items()}
    return o


def _safe_json_dumps(obj):
    """JSON 序列化（assume 数据已在入库时清洗过；allow_nan=False 双保险）"""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


# ============== DevTools HTTP 服务 ==============

class HTMLRequestHandler(BaseHTTPRequestHandler):
    """DevTools HTML 界面请求处理器"""

    def log_message(self, format, *args):
        pass

    @staticmethod
    def _is_safe_origin(origin):
        """检查 origin 是否为安全的本地来源（防止 localhost.evil.com 绕过）"""
        if not origin:
            return False
        # 精确匹配（无端口）或前缀匹配后跟 : 或 /（有端口或路径）
        for prefix in ('http://localhost', 'http://127.0.0.1'):
            if origin == prefix:
                return True
            if origin.startswith(prefix) and len(origin) > len(prefix) and origin[len(prefix)] in (':', '/'):
                return True
        return False

    def _set_cors(self):
        """设置 CORS 头 — 仅允许本地 origin（边界检查，防止 localhost.evil.com 绕过）"""
        origin = self.headers.get('Origin', '')
        if self._is_safe_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)

    def _send_json(self, data, allow_gzip=True):
        """发送 JSON 响应，支持 gzip 压缩"""
        body = _safe_json_dumps(data).encode('utf-8')
        use_gzip = (
            allow_gzip
            and len(body) > 1024
            and 'gzip' in (self.headers.get('Accept-Encoding') or '')
        )
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self._set_cors()
        if use_gzip:
            body = gzip.compress(body)
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
            self._set_cors()
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_error(404)

    def serve_html(self):
        """返回 DevTools HTML 页面"""
        html = get_html()
        body = html.encode('utf-8')
        use_gzip = 'gzip' in (self.headers.get('Accept-Encoding') or '')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self._set_cors()
        if use_gzip and len(body) > 1024:
            body = gzip.compress(body)
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_logs_json(self, parsed):
        """返回日志 JSON 数据（支持筛选参数 + gzip）"""
        params = urllib.parse.parse_qs(parsed.query)
        since_id = params.get('since', [None])[0]
        if since_id is not None:
            try:
                since_id = int(since_id)
            except (ValueError, TypeError):
                since_id = None

        method_filter = params.get('method', [None])[0]
        status_filter = params.get('status', [None])[0]

        logs, full_reset = log_buffer.get_all(since_id, method_filter, status_filter)
        stats = log_buffer.get_stats()

        self.send_response(200)
        self._send_json({'stats': stats, 'logs': logs, 'full_reset': full_reset})


class ReusableHTTPServer(HTTPServer):
    """支持 SO_REUSEADDR 的 HTTPServer，避免 TIME_WAIT 导致端口绑定失败"""
    allow_reuse_address = True
    allow_reuse_port = True


def _kill_port_process(port):
    """强制释放被占用的端口（Windows 平台）"""
    import subprocess
    try:
        # Windows netstat 输出是 GBK 编码
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, timeout=5
        )
        output = result.stdout.decode("gbk", errors="replace")
        current_pid = str(os.getpid())
        killed = []
        for line in output.splitlines():
            # 匹配 :port LISTENING（只杀监听进程）
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1].strip()
                    if pid.isdigit() and pid != "0" and pid != current_pid:
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True, timeout=5
                            )
                            killed.append(pid)
                        except Exception:
                            pass
        if killed:
            cprint(f"  已强制释放端口 {port} (PID: {', '.join(killed)})", Colors.DIM)
            return True
        return False
    except Exception as e:
        safe_print(f"  端口释放失败: {e}", Colors.DIM)
        return False


def start_html_server(port):
    """启动 HTML DevTools 服务，强制使用指定端口"""
    server = None
    actual_port = port
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            server = ReusableHTTPServer(('127.0.0.1', port), HTMLRequestHandler)
            actual_port = port
            break
        except (PermissionError, OSError) as e:
            if attempt < max_attempts - 1:
                # 尝试强制释放端口
                cprint(f"  端口 {port} 被占用，尝试强制释放 (第{attempt+1}次)...", Colors.YELLOW)
                if _kill_port_process(port):
                    time.sleep(1.5)  # 等待端口完全释放
                    continue
                else:
                    # 没找到占用进程，可能是 Windows 保留端口范围
                    time.sleep(1.0)
                    continue
            else:
                cprint(f"  端口 {port} 被占用，无法释放", Colors.RED)
                raise

    if server is None:
        raise RuntimeError(f"无法绑定端口 {port}，请手动检查端口占用情况")

    def _run_server():
        try:
            server.serve_forever()
        except Exception as e:
            safe_print(f"  HTML 服务异常: {e}", Colors.RED)

    thread = threading.Thread(target=_run_server, daemon=True)
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
