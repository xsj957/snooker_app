#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DB Query Tool — MySQL 实时查询工具
功能: HTML 界面执行 SELECT 查询，只读模式，仅限 supervisions 库
用法: python dbtools/server.py [--port 8900] [--host 127.0.0.1]
"""

import os
import sys
import json
import time
import re
import threading
import argparse
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date

# ============== 数据库配置 ==============

DB_CONFIG = {
    'host': '121.40.243.17',
    'port': 3306,
    'user': 'linjiakun',
    'password': 'Ljk@123456',
    'database': 'supervisions',
    'charset': 'utf8mb4',
    'connect_timeout': 10,
    'read_timeout': 30,
}

# ============== SQL 安全校验 ==============

FORBIDDEN_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
    'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 'SET', 'LOAD',
    'CALL', 'EXEC', 'EXECUTE', 'MERGE', 'LOCK', 'UNLOCK',
]

FORBIDDEN_PHRASES = [
    'INTO OUTFILE', 'INTO DUMPFILE', 'INTO @',
]

ALLOWED_FIRST_WORDS = ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']


def validate_query(sql):
    """校验 SQL 安全性，返回 (ok, error_message)"""
    if not sql or not sql.strip():
        return False, "SQL 不能为空"

    # 去除注释
    cleaned = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    if not cleaned:
        return False, "SQL 不能为空"

    upper = cleaned.upper()

    # 禁止多语句
    stmts = [s.strip() for s in cleaned.split(';') if s.strip()]
    if len(stmts) > 1:
        return False, "禁止多语句查询，一次只允许一条 SQL"

    # 检查首词
    first_word = upper.split()[0] if upper.split() else ''
    if first_word not in ALLOWED_FIRST_WORDS:
        return False, f"仅支持 {', '.join(ALLOWED_FIRST_WORDS)} 语句"

    # 检查危险关键词（仅 SELECT 语句体内，跳过首词）
    body = ' '.join(upper.split()[1:]) if len(upper.split()) > 1 else ''
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + kw + r'\b', body):
            return False, f"禁止使用关键词: {kw}"

    for phrase in FORBIDDEN_PHRASES:
        if phrase in upper:
            return False, f"禁止使用: {phrase}"

    return True, ""


def auto_limit(sql, max_rows=1000):
    """如果没有 LIMIT，自动追加"""
    upper = sql.strip().upper()
    if upper.startswith('SELECT') and 'LIMIT' not in upper:
        return sql.rstrip().rstrip(';') + f' LIMIT {max_rows}'
    return sql


# ============== 数据库查询 ==============

def _serialize_row(row):
    """将行数据序列化为 JSON 兼容类型"""
    result = []
    for val in row:
        if isinstance(val, (datetime, date)):
            result.append(val.strftime('%Y-%m-%d %H:%M:%S'))
        elif isinstance(val, bytes):
            result.append(val.hex())
        elif isinstance(val, (int, float, type(None))):
            result.append(val)
        else:
            result.append(str(val))
    return result


def execute_query(sql):
    """执行查询，返回 {columns, rows, count, time_ms, error}"""
    ok, err = validate_query(sql)
    if not ok:
        return {'columns': [], 'rows': [], 'count': 0, 'time_ms': 0, 'error': err}

    sql = auto_limit(sql)

    try:
        import pymysql
    except ImportError:
        return {'columns': [], 'rows': [], 'count': 0, 'time_ms': 0,
                'error': "pymysql 未安装，请执行: pip install pymysql"}

    conn = None
    start = time.time()
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute(sql)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [_serialize_row(r) for r in cursor.fetchall()]
            else:
                columns = ['result']
                rows = [[f"Affected rows: {cursor.rowcount}"]]
            elapsed = round((time.time() - start) * 1000, 1)
            return {
                'columns': columns,
                'rows': rows,
                'count': len(rows),
                'time_ms': elapsed,
                'error': None,
            }
    except pymysql.err.ProgrammingError as e:
        elapsed = round((time.time() - start) * 1000, 1)
        return {'columns': [], 'rows': [], 'count': 0, 'time_ms': elapsed,
                'error': f"SQL 语法错误: {e}"}
    except pymysql.err.OperationalError as e:
        elapsed = round((time.time() - start) * 1000, 1)
        return {'columns': [], 'rows': [], 'count': 0, 'time_ms': elapsed,
                'error': f"数据库连接错误: {e}"}
    except Exception as e:
        elapsed = round((time.time() - start) * 1000, 1)
        return {'columns': [], 'rows': [], 'count': 0, 'time_ms': elapsed,
                'error': str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_tables():
    """获取所有表名及行数"""
    sql = """
        SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'supervisions'
        ORDER BY TABLE_NAME
    """
    result = execute_query(sql)
    if result['error']:
        return []
    tables = []
    for row in result['rows']:
        tables.append({
            'name': row[0],
            'rows': row[1] or 0,
            'comment': row[2] or '',
        })
    return tables


def get_table_schema(table_name):
    """获取表结构"""
    # 安全校验表名
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        return {'error': '非法表名'}
    sql = f"SHOW FULL COLUMNS FROM `{table_name}`"
    return execute_query(sql)


# ============== 常用查询模板 ==============

QUERY_CATALOG = [
    {
        "group": "用户查询",
        "items": [
            {"name": "用户基本信息", "sql": "SELECT * FROM ten_user WHERE id = '{user_id}'"},
            {"name": "通过UnionID查用户", "sql": "SELECT * FROM ten_user WHERE union_id = '{union_id}'"},
            {"name": "用户授权登录", "sql": "SELECT * FROM ten_user_auth WHERE user_id = '{user_id}'"},
            {"name": "用户扩展信息", "sql": "SELECT * FROM ten_user_ext WHERE user_id = '{user_id}'"},
            {"name": "用户资产余额", "sql": "SELECT * FROM pay_user WHERE union_id = '{union_id}'"},
        ]
    },
    {
        "group": "视频券",
        "items": [
            {"name": "用户所有视频券", "sql": "SELECT * FROM video_coupon_record WHERE user_id = '{user_id}' ORDER BY draw_time DESC"},
            {"name": "有效券数量", "sql": "SELECT COUNT(*) AS valid_count FROM video_coupon_record WHERE user_id = '{user_id}' AND status = 0"},
            {"name": "即将过期券(7天内)", "sql": "SELECT * FROM video_coupon_record WHERE user_id = '{user_id}' AND status = 0 AND end_date BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY) ORDER BY end_date"},
            {"name": "已过期但状态未更新", "sql": "SELECT * FROM video_coupon_record WHERE status = 0 AND end_date < NOW()"},
            {"name": "按券ID查询", "sql": "SELECT * FROM video_coupon_record WHERE id = {id}"},
        ]
    },
    {
        "group": "视频订单",
        "items": [
            {"name": "用户所有视频订单", "sql": "SELECT * FROM video_order WHERE user_id = '{user_id}' ORDER BY create_time DESC"},
            {"name": "现金解锁视频", "sql": "SELECT * FROM video_order WHERE user_id = '{user_id}' AND pay_status = '支付成功' AND (combo_order_id IS NULL OR combo_order_id = 0)"},
            {"name": "券解锁视频", "sql": "SELECT * FROM video_order WHERE user_id = '{user_id}' AND pay_status = '支付成功' AND combo_order_id IS NOT NULL AND combo_order_id > 0"},
            {"name": "App端购买记录", "sql": "SELECT * FROM video_order WHERE pay_channel IN (2, 3)"},
            {"name": "已支付未观看", "sql": "SELECT * FROM video_order WHERE user_id = '{user_id}' AND pay_status = '支付成功' AND is_viewed = 0"},
            {"name": "重复订单检测", "sql": "SELECT user_id, video_id, COUNT(*) AS cnt FROM video_order WHERE pay_status = '支付成功' GROUP BY user_id, video_id HAVING cnt > 1"},
        ]
    },
    {
        "group": "套餐订单",
        "items": [
            {"name": "用户套餐订单", "sql": "SELECT * FROM video_combo_order WHERE user_id = '{user_id}' ORDER BY create_time DESC"},
            {"name": "套餐定义", "sql": "SELECT * FROM video_combo WHERE status = 1 ORDER BY display_order"},
            {"name": "已过期套餐", "sql": "SELECT * FROM video_combo_order WHERE end_time IS NOT NULL AND end_time < NOW() AND pay_status = '支付成功'"},
        ]
    },
    {
        "group": "视频制作状态",
        "items": [
            {"name": "各状态视频数量统计", "sql": "SELECT status, COUNT(*) AS cnt FROM video_client_status GROUP BY status ORDER BY status"},
            {"name": "下载失败视频", "sql": "SELECT * FROM video_client_status WHERE status = 4 ORDER BY updated_at DESC"},
            {"name": "制作失败视频", "sql": "SELECT * FROM video_client_status WHERE status = 6 ORDER BY updated_at DESC"},
            {"name": "按设备查视频状态", "sql": "SELECT * FROM video_client_status WHERE client_id = '{device_udid}' ORDER BY updated_at DESC"},
        ]
    },
    {
        "group": "视频目录",
        "items": [
            {"name": "视频详情", "sql": "SELECT * FROM video_list WHERE id = {video_id}"},
            {"name": "按分类统计", "sql": "SELECT category, COUNT(*) AS cnt, SUM(buy_times) AS total_buys, SUM(amount)/100 AS total_revenue_yuan FROM video_list GROUP BY category ORDER BY total_revenue_yuan DESC"},
            {"name": "视频原片地址", "sql": "SELECT * FROM video_source WHERE order_id = {video_id}"},
        ]
    },
    {
        "group": "退款",
        "items": [
            {"name": "用户退款记录", "sql": "SELECT * FROM video_refund WHERE user_id = '{user_id}' ORDER BY create_time DESC"},
            {"name": "退款失败记录", "sql": "SELECT * FROM video_refund WHERE status = 3 ORDER BY create_time DESC"},
            {"name": "待审核退款", "sql": "SELECT * FROM video_refund WHERE status = 0 ORDER BY create_time"},
        ]
    },
    {
        "group": "数据统计",
        "items": [
            {"name": "全量业务概览", "sql": "SELECT (SELECT COUNT(*) FROM video_list) AS total_videos, (SELECT COUNT(*) FROM video_order WHERE pay_status='支付成功') AS paid_orders, (SELECT SUM(amount)/100 FROM video_order WHERE pay_status='支付成功') AS total_revenue_yuan, (SELECT COUNT(*) FROM video_coupon_record WHERE status=0) AS valid_coupons, (SELECT COUNT(*) FROM video_client_status WHERE status=7) AS completed_videos"},
            {"name": "购买渠道分布", "sql": "SELECT pay_channel, COUNT(*) AS order_count, SUM(amount)/100 AS revenue_yuan FROM video_order WHERE pay_status = '支付成功' GROUP BY pay_channel ORDER BY order_count DESC"},
            {"name": "每日解锁趋势(近30天)", "sql": "SELECT DATE(create_time) AS date, COUNT(*) AS total, SUM(CASE WHEN pay_status='支付成功' THEN 1 ELSE 0 END) AS paid, SUM(CASE WHEN pay_status='支付成功' THEN amount ELSE 0 END)/100 AS revenue_yuan FROM video_order GROUP BY DATE(create_time) ORDER BY date DESC LIMIT 30"},
            {"name": "播放排行Top20", "sql": "SELECT video_id, COUNT(*) AS play_events, SUM(play_count) AS total_plays FROM video_event GROUP BY video_id ORDER BY total_plays DESC LIMIT 20"},
            {"name": "定价规则", "sql": "SELECT * FROM video_price WHERE is_regular = 1 ORDER BY category"},
        ]
    },
    {
        "group": "问题排查",
        "items": [
            {"name": "已支付但无原片", "sql": "SELECT vo.* FROM video_order vo LEFT JOIN video_source vs ON vo.video_id = vs.order_id WHERE vo.pay_status = '支付成功' AND vs.id IS NULL"},
            {"name": "状态不一致视频", "sql": "SELECT vo.id, vo.video_id, vo.video_status AS order_status, vcs.status AS client_status FROM video_order vo LEFT JOIN video_client_status vcs ON vo.video_id = vcs.video_id WHERE vo.video_status != 0 AND (vcs.status IS NULL OR vcs.status = 0)"},
            {"name": "有券未使用的用户", "sql": "SELECT u.id, u.nickname, COUNT(vcr.id) AS total_coupons, SUM(CASE WHEN vcr.status=0 THEN 1 ELSE 0 END) AS unused FROM ten_user u JOIN video_coupon_record vcr ON u.id = vcr.user_id GROUP BY u.id, u.nickname HAVING unused > 0 ORDER BY unused DESC LIMIT 20"},
            {"name": "套餐已支付但券未到账", "sql": "SELECT vco.*, (SELECT COUNT(*) FROM video_coupon_record WHERE user_id = vco.user_id AND draw_time >= vco.create_time) AS coupons_after_purchase FROM video_combo_order vco WHERE vco.pay_status = '支付成功' AND vco.used_count = 0 ORDER BY vco.create_time DESC"},
            {"name": "视频超48h未解锁", "sql": "SELECT vo.id, vo.video_id, vo.user_id, vo.create_time, TIMESTAMPDIFF(HOUR, vo.create_time, NOW()) AS hours FROM video_order vo LEFT JOIN video_client_status vcs ON vo.video_id = vcs.video_id WHERE vo.pay_status = '支付成功' AND (vcs.status = 0 OR vcs.status IS NULL) AND TIMESTAMPDIFF(HOUR, vo.create_time, NOW()) > 48"},
        ]
    },
]


# ============== HTML 模板 ==============

def get_html():
    # 支持直接运行 python dbtools/server.py 和作为模块导入两种情况
    try:
        from dbtools.html_template import DBTOOLS_HTML
    except ImportError:
        # 直接运行时 dbtools 包不在 sys.path 中，从同级目录导入
        from html_template import DBTOOLS_HTML
    return DBTOOLS_HTML


# ============== HTTP 服务 ==============

class DBRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def handle_one_request(self):
        """Override to catch and log exceptions"""
        try:
            super().handle_one_request()
        except Exception as e:
            print(f"Handler error: {type(e).__name__}: {e}", flush=True)

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code, msg):
        self._send_json({'error': msg, 'code': code}, code=code)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ('/', '/index.html'):
            self._serve_html()
        elif path == '/api/tables':
            self._serve_tables()
        elif path.startswith('/api/schema/'):
            table = path[len('/api/schema/'):]
            self._serve_schema(table)
        elif path == '/api/catalog':
            self._serve_catalog()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/query':
            self._handle_query()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _serve_html(self):
        html = get_html()
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_tables(self):
        tables = get_tables()
        self._send_json({'tables': tables})

    def _serve_schema(self, table_name):
        result = get_table_schema(table_name)
        self._send_json(result)

    def _serve_catalog(self):
        self._send_json({'catalog': QUERY_CATALOG})

    def _handle_query(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            sql = data.get('sql', '').strip()
            result = execute_query(sql)
            self._send_json(result)
        except json.JSONDecodeError:
            self._send_error(400, '请求体 JSON 格式错误')
        except Exception as e:
            self._send_error(500, str(e))


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True
    # allow_reuse_port only works on some platforms
    try:
        allow_reuse_port = True
    except Exception:
        pass


# ============== 测试用户数据 ==============

TEST_USERS = [
    {
        "name": "用户A (ice)",
        "user_id": "aff7eae4-3680-4b89-9f01-819e02c3b6b5",
        "phone": "17620885381",
        "union_id": "oIp-Q5pI-MlZ2Lov0zX-cIhs4caw",
    },
    {
        "name": "用户B (Natural)",
        "user_id": "57d703dc-659a-4474-898e-b75efa1f2e0a",
        "phone": "13538506002",
        "union_id": "oIp-Q5uHh1HHD4UBBSr51Y2b_0KE",
    },
    {
        "name": "用户C",
        "user_id": "7c37a4a2-d11a-4ac8-83c6-b7c293b6c1f4",
        "phone": "19928710361",
        "union_id": "oIp-Q5qUwi6ULEGjTchV6FRL3xhc",
    },
]


# ============== CLI ==============

def main():
    # Windows 终端 UTF-8 输出
    import io
    try:
        if sys.stdout and hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description='DB Query Tool - supervisions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dbtools/server.py                # default localhost:8900
  python dbtools/server.py --port 9000    # custom port
        """
    )
    parser.add_argument('--host', default='127.0.0.1', help='Listen address (default 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8900, help='Port (default 8900)')
    args = parser.parse_args()

    # Bind port
    server = None
    actual_port = args.port
    for p in [args.port, args.port + 1, args.port + 2]:
        try:
            server = ReusableHTTPServer((args.host, p), DBRequestHandler)
            actual_port = p
            break
        except OSError:
            continue

    if server is None:
        print(f"\n  Error: Cannot bind port {args.port}")
        sys.exit(1)

    print()
    print(f"  +==========================================+")
    print(f"  |   DB Query Tool - supervisions           |")
    print(f"  +==========================================+")
    print(f"  |   http://{args.host}:{actual_port:<5}                    |")
    print(f"  |                                          |")
    print(f"  |   DB: {DB_CONFIG['host']}:{DB_CONFIG['port']}               |")
    print(f"  |   Mode: READ ONLY (SELECT/SHOW/DESC)     |")
    print(f"  |                                          |")
    print(f"  |   Ctrl+C to stop                         |")
    print(f"  +==========================================+")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止")
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
