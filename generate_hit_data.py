#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量插入 ten_hit_info_simple 数据（随机数据版）
- 从 ten_user 表获取前 500 个用户
- 每个用户插入 500 条随机击球数据
- 总计 250,000 行
"""

import pymysql
import random
from datetime import datetime, timedelta

# ============== 数据库配置 ==============
DB_CONFIG = {
    'host': '121.40.243.17',
    'port': 3306,
    'user': 'linjiakun',
    'password': 'Ljk@123456',
    'database': 'supervisions',
    'charset': 'utf8mb4',
    'connect_timeout': 10,
}

USER_COUNT = 500       # 用户数
RECORDS_PER_USER = 500 # 每个用户的记录数
BATCH_USERS = 10       # 每批处理的用户数（10用户 × 500条 = 5000行/批）
CLUB = "葱子的俱乐部"
COMPETITION_ID = "xsj_test_2026"


def rand_score():
    """生成随机 score 字符串，如 '1,7,-3,1,4,1,6,...'"""
    length = random.randint(12, 36)
    nums = []
    for _ in range(length):
        # 80% 概率为正数 1~7，20% 概率为负数 -5~-1
        if random.random() < 0.8:
            nums.append(str(random.randint(1, 7)))
        else:
            nums.append(str(random.randint(-5, -1)))
    return ",".join(nums)


def rand_time():
    """生成随机时间（2026-01 ~ 2026-09）"""
    start = datetime(2026, 1, 1)
    end = datetime(2026, 9, 15, 23, 59, 59)
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return (start + timedelta(seconds=random_seconds)).strftime("%Y-%m-%d %H:%M:%S")


def rand_pair(max_num=10):
    """生成 (num, den) 数对，num <= den"""
    den = random.randint(1, max_num)
    num = random.randint(0, den)
    return num, den


def generate_record(frame):
    """生成一条随机击球记录"""
    score = rand_score()
    time = rand_time()
    rest = rand_pair(6)
    aroundball = rand_pair(10)
    mentality = rand_pair(8)
    far_attack = rand_pair(8)
    defence = rand_pair(8)
    final_round = rand_pair(3)
    reversal = rand_pair(3)
    table_time = random.randint(200, 1500)
    attack = rand_pair(40)
    return (frame, score, time,
            rest[0], rest[1],
            aroundball[0], aroundball[1],
            mentality[0], mentality[1],
            far_attack[0], far_attack[1],
            defence[0], defence[1],
            final_round[0], final_round[1],
            reversal[0], reversal[1],
            table_time,
            attack[0], attack[1])


def get_user_ids(limit=USER_COUNT):
    """从 ten_user 表获取前 N 个用户 ID"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ten_user ORDER BY id LIMIT %s", (limit,))
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return user_ids


def build_insert_sql(user_ids):
    """为一批用户构建批量 INSERT 语句（随机数据）"""
    rows = []
    for uid in user_ids:
        for frame in range(1, RECORDS_PER_USER + 1):
            rec = generate_record(frame)
            row = (
                f"('{uid}', '{CLUB}', '{COMPETITION_ID}', {rec[0]}, "
                f"'{rec[1]}', '{rec[2]}', "
                f"{rec[3]},{rec[4]}, {rec[5]},{rec[6]}, {rec[7]},{rec[8]}, "
                f"{rec[9]},{rec[10]}, {rec[11]},{rec[12]}, "
                f"{rec[13]},{rec[14]}, {rec[15]},{rec[16]}, "
                f"{rec[17]}, {rec[18]},{rec[19]})"
            )
            rows.append(row)

    sql = "INSERT INTO `ten_hit_info_simple` (\n"
    sql += "      `id`, `club`, `competitionId`, `frame`, `score`, `time`,\n"
    sql += "      `restNum`, `restDen`, `aroundballNum`, `aroundballDen`,\n"
    sql += "      `mentalityNum`, `mentalityDen`, `farAttackNum`, `farAttackDen`,\n"
    sql += "      `defenceNum`, `defenceDen`, `finalRoundNum`, `finalRoundDen`,\n"
    sql += "      `reversalNum`, `reversalDen`, `tableTime`, `attackNum`, `attackDen`\n"
    sql += "  ) VALUES\n"
    sql += ",\n".join(rows) + ";"
    return sql


def main():
    print(f"正在从 ten_user 表获取前 {USER_COUNT} 个用户...")
    user_ids = get_user_ids(USER_COUNT)
    print(f"获取到 {len(user_ids)} 个用户")

    total_rows = len(user_ids) * RECORDS_PER_USER
    print(f"将插入 {len(user_ids)} 个用户 × {RECORDS_PER_USER} 条数据 = {total_rows:,} 行")

    total_batches = (len(user_ids) + BATCH_USERS - 1) // BATCH_USERS
    success_count = 0
    fail_count = 0

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_USERS
        end = min(start + BATCH_USERS, len(user_ids))
        batch_ids = user_ids[start:end]

        sql = build_insert_sql(batch_ids)

        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            conn.commit()
            success_count += len(batch_ids)
            done = success_count + fail_count
            pct = done / len(user_ids) * 100
            print(f"  ✅ 批次 {batch_idx+1}/{total_batches} ({pct:.0f}%): "
                  f"插入 {len(batch_ids)} 个用户（{len(batch_ids)*RECORDS_PER_USER:,} 行）")
        except Exception as e:
            fail_count += len(batch_ids)
            print(f"  ❌ 批次 {batch_idx+1}/{total_batches}: 失败 — {e}")
            conn.rollback()
        finally:
            conn.close()

    print(f"\n{'='*50}")
    print(f"完成！成功: {success_count} 用户, 失败: {fail_count} 用户")
    print(f"总插入行数: {success_count * RECORDS_PER_USER:,}")


if __name__ == "__main__":
    main()
