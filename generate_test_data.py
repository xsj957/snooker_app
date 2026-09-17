#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成并插入 ten_hit_info_simple 测试数据
500 个用户 × 每人 1000 条记录 = 50 万条
分批插入（每批 1000 条），避免超出 max_allowed_packet
"""

import random
import pymysql

# ==================== 数据库配置 ====================
DB_CONFIG = {
    'host': '121.40.243.17',
    'port': 3306,
    'user': 'linjiakun',
    'password': 'Ljk@123456',
    'database': 'supervisions',
    'charset': 'utf8mb4',
}

# ==================== 数据模板配置 ====================
CLUB_NAME = '葱子的俱乐部'
COMPETITION_ID = 'SIM_Tournament_2026'
BASE_TIME = '2026-09-15 23:59:59'
USER_COUNT = 500              # 从 ten_user 表查询的用户数量
FRAMES_PER_USER = 500      # 每个用户生成 1000 条记录
BATCH_SIZE = 100        # 每批插入的记录数

# ==================== 数据生成函数 ====================
def generate_score_string():
    """生成随机的得分字符串（每杆得分情况）"""
    score_parts = []
    num_shots = random.randint(10, 40)

    shot_types = ['1,7', '1,6', '1,5', '1,4', '-1', '-2', '-3', '-4']
    weights = [40, 20, 15, 10, 5, 4, 3, 3]

    for _ in range(num_shots):
        shot_type = random.choices(shot_types, weights=weights)[0]
        score_parts.append(shot_type)

    return ','.join(score_parts)


def generate_record(user_id, frame_num):
    """生成单条记录"""
    return (
        user_id,                                  # id - 用户id
        CLUB_NAME,                                  # club - 俱乐部
        COMPETITION_ID,                             # competitionId - 比赛id
        frame_num,                                  # frame - 第几局
        generate_score_string(),                    # score - 每杆得分情况
        BASE_TIME,                                  # time - 工控机上报时间
        random.randint(0, 5),                       # restNum - 架杆分子
        random.randint(1, 10),                      # restDen - 架杆分母
        random.randint(0, 10),                      # aroundballNum - 围球分子
        random.randint(1, 15),                      # aroundballDen - 围球分母
        random.randint(0, 8),                       # mentalityNum - 心态分子
        random.randint(1, 15),                      # mentalityDen - 心态分母
        random.randint(0, 6),                       # farAttackNum - 长台能力分子
        random.randint(1, 10),                      # farAttackDen - 长台能力分母
        random.randint(0, 5),                       # defenceNum - 防守能力分子
        random.randint(1, 10),                      # defenceDen - 防守能力分母
        random.randint(0, 2),                       # finalRoundNum - 决胜局获胜率分子
        random.randint(1, 3),                       # finalRoundDen - 决胜局获胜率分母
        random.randint(0, 1),                       # reversalNum - 逆转分子
        random.randint(1, 3),                       # reversalDen - 逆转分母
        random.randint(300, 1500),                  # tableTime - 台面时长
        random.randint(5, 40),                      # attackNum - 进攻分子
        random.randint(5, 50),                      # attackDen - 进攻分母
    )


def main():
    total_records = USER_COUNT * FRAMES_PER_USER
    total_batches = (total_records + BATCH_SIZE - 1) // BATCH_SIZE

    print("=" * 80)
    print("生成测试数据")
    print("=" * 80)
    print(f"俱乐部:       {CLUB_NAME}")
    print(f"比赛ID:       {COMPETITION_ID}")
    print(f"时间:         {BASE_TIME}")
    print(f"用户数量:     {USER_COUNT}")
    print(f"每用户记录数: {FRAMES_PER_USER}")
    print(f"总记录数:     {total_records:,}")
    print(f"每批大小:     {BATCH_SIZE}")
    print(f"总批次数:     {total_batches}")
    print()

    # 连接数据库查询 user_id
    print("正在查询 ten_user 表...")
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT id FROM ten_user ORDER BY id LIMIT {USER_COUNT}")
            user_ids = [row[0] for row in cursor.fetchall()]
        connection.close()
        print(f"✓ 获取到 {len(user_ids)} 个 user_id")
    except Exception as e:
        print(f"✗ 查询失败: {e}")
        return

    # 打印预览（前 3 个用户各前 2 条）
    print()
    print("=" * 80)
    print("数据预览（前 3 个用户 × 各 2 条）：")
    print("=" * 80)
    sample_records = []
    for uid in user_ids[:3]:
        for f in range(1, 3):
            sample_records.append(generate_record(uid, f))

    for i, record in enumerate(sample_records, 1):
        print(f"\n记录 {i}: user_id={record[0][:8]}... frame={record[3]} score={record[4][:30]}...")

    print()
    print("=" * 80)
    print("即将开始分批插入（每批 1000 条，共约 500 批）")
    print("按 Enter 继续，或按 Ctrl+C 取消")
    print("=" * 80)

    input("按 Enter 继续...")

    # 连接数据库执行分批插入
    print("\n正在连接数据库...")
    try:
        connection = pymysql.connect(**DB_CONFIG)
        print("✓ 数据库连接成功")

        columns = (
            'id, club, competitionId, frame, score, time, '
            'restNum, restDen, aroundballNum, aroundballDen, '
            'mentalityNum, mentalityDen, farAttackNum, farAttackDen, '
            'defenceNum, defenceDen, finalRoundNum, finalRoundDen, '
            'reversalNum, reversalDen, tableTime, attackNum, attackDen'
        )

        total_inserted = 0
        frame_counter = 1

        for batch_idx in range(total_batches):
            batch_records = []
            for _ in range(BATCH_SIZE):
                if frame_counter > total_records:
                    break
                # 计算当前 record 属于哪个用户
                user_idx = (frame_counter - 1) // FRAMES_PER_USER
                user_id = user_ids[user_idx]
                frame_in_user = (frame_counter - 1) % FRAMES_PER_USER + 1
                batch_records.append(generate_record(user_id, frame_in_user))
                frame_counter += 1

            if not batch_records:
                break

            # 构建 INSERT SQL
            value_list = []
            for record in batch_records:
                values = ', '.join([f"'{v}'" if isinstance(v, str) else str(v) for v in record])
                value_list.append(f"({values})")

            sql = f"INSERT INTO `ten_hit_info_simple` ({columns}) VALUES\n" + ',\n'.join(value_list) + ';'

            with connection.cursor() as cursor:
                cursor.execute(sql)

            connection.commit()
            total_inserted += len(batch_records)

            progress = (batch_idx + 1) / total_batches * 100
            print(f"  批次 {batch_idx + 1}/{total_batches} | "
                  f"已插入 {total_inserted:,}/{total_records:,} ({progress:.1f}%)", end='\r')

        print(f"\n\n✓ 全部完成！共插入 {total_inserted:,} 条记录")

    except pymysql.Error as e:
        print(f"\n✗ 数据库错误: {e}")
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()
            print("✓ 数据库连接已关闭")


if __name__ == '__main__':
    main()
