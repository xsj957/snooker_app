# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from copy import copy
from datetime import datetime

src = 'iter-v1.0.1-第二期/测试用例-20260909_2340.xlsx'
wb = openpyxl.load_workbook(src)

def insert_tc(ws, after_row, tc_data):
    ws.insert_rows(after_row + 1)
    for c in range(1, 21):
        ref = ws.cell(row=after_row, column=c)
        cell = ws.cell(row=after_row + 1, column=c)
        cell.font = copy(ref.font)
        cell.fill = copy(ref.fill)
        cell.border = copy(ref.border)
        cell.alignment = copy(ref.alignment)
    for col_idx, val in tc_data.items():
        ws.cell(row=after_row + 1, column=col_idx).value = val

def find_row(ws, col1_key=None, col5_key=None, col6_key=None):
    for r in range(2, ws.max_row + 1):
        a = str(ws.cell(row=r, column=1).value or '')
        e = str(ws.cell(row=r, column=5).value or '')
        f = str(ws.cell(row=r, column=6).value or '')
        if col1_key and col1_key in a:
            return r
        if col5_key and col5_key in e:
            return r
        if col6_key and col6_key in f:
            return r
    return None

def renumber_sheet(ws):
    prefix = '斯诺克大师V1.0.1-'
    counter = 1
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(row=r, column=1).value or '')
        if val.startswith(prefix) or val == 'PLACEHOLDER':
            ws.cell(row=r, column=1).value = f'{prefix}{counter:04d}'
            counter += 1
    return counter - 1

# ============================================================
# STEP 1: Delete duplicates from iOS (bottom-up)
# ============================================================
ws_ios = wb['国内iOS']
ws_and = wb['安卓']

# Delete 0121 and 0122 (video券落地页 + unlock popup in legacy section)
row_122 = find_row(ws_ios, col1_key='-0122')
row_121 = find_row(ws_ios, col1_key='-0121')

print('=== STEP 1: 删除重复用例 ===')
if row_122:
    print(f'  删除 iOS 0122: {ws_ios.cell(row=row_122, column=6).value}')
    ws_ios.delete_rows(row_122)
if row_121:
    print(f'  删除 iOS 0121: {ws_ios.cell(row=row_121, column=6).value}')
    ws_ios.delete_rows(row_121)

# Renumber after deletion
renumber_sheet(ws_ios)
print('  iOS重新编号完成')

# ============================================================
# STEP 2: Modify types (功能→UI) in iOS
# ============================================================
print('\n=== STEP 2: 修改用例类型 ===')
# After deletion, old 0119 is now 0119 (still) since deletions were above it
# Actually 0121/0122 deleted, 0119 stays 0119
row_0119 = find_row(ws_ios, col1_key='-0119')
if row_0119:
    old_type = ws_ios.cell(row=row_0119, column=4).value
    ws_ios.cell(row=row_0119, column=4).value = 'UI'
    print(f'  iOS R{row_0119}: 功能→UI ({ws_ios.cell(row=row_0119, column=5).value})')

# ============================================================
# STEP 3: Insert new cases - Android (bottom-up within sections)
# ============================================================
print('\n=== STEP 3: 新增安卓用例 ===')

# AND-1: 消息推送: 通知时机-App在前台不推送 → after 首次安装App通知权限请求(0101)
row = find_row(ws_and, col1_key='-0101')
if row:
    insert_tc(ws_and, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: '功能',
        5: '通知时机-App在前台不推送',
        6: 'App在前台运行时不推送通知，仅后台或离开时推送',
        7: '用户已授权通知权限，App在前台运行',
        8: '1.打开App并保持在前台运行\n2.触发比赛结束事件（后台产生推送）\n3.观察App前台是否收到推送通知\n4.将App退入后台，再次触发事件，观察是否收到推送',
        9: '1.App在前台运行\n2.事件已触发\n3.App在前台时不收到推送通知\n4.App在后台时正常收到推送通知',
        10: 'P1',
    })
    print(f'  安卓 R{row+1}: 通知时机-App在前台不推送')

# AND-2: 消息推送: 比赛结果通知-点击跳转 → after 比赛结果通知推送(0102)
row = find_row(ws_and, col1_key='-0102')
if row:
    insert_tc(ws_and, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: '功能',
        5: '比赛结果通知-点击跳转',
        6: '点击比赛结果通知跳转到场详情页视频回放tab',
        7: '用户已授权通知权限，App不在前台',
        8: '1.比赛结束后收到推送通知\n2.点击通知条\n3.检查跳转目标页面',
        9: '1.收到标题“比赛结果通知”的推送\n2.App被唤起并跳转\n3.跳转到对应比赛的场详情页→视频回放tab',
        10: 'P1',
    })
    print(f'  安卓 R{row+1}: 比赛结果通知-点击跳转')

# ============================================================
# STEP 4: Insert new cases - iOS (bottom-up)
# ============================================================
print('\n=== STEP 4: 新增iOS用例 ===')

# iOS-1: 消息推送: App在前台不推送 → after 首次安装App通知权限请求(0092)
row = find_row(ws_ios, col1_key='-0092')
if row:
    insert_tc(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: '功能',
        5: '通知时机-App在前台不推送',
        6: 'App在前台运行时不推送通知，仅后台或离开时推送',
        7: '用户已授权通知权限，App在前台运行',
        8: '1.打开App并保持在前台运行\n2.触发比赛结束事件\n3.观察App前台是否收到推送\n4.App退入后台再次触发事件',
        9: '1.App在前台运行\n2.事件已触发\n3.App在前台时不收到APNs推送\n4.后台时正常收到APNs推送',
        10: 'P1',
    })
    print(f'  iOS R{row+1}: 通知时机-App在前台不推送')

# iOS-2: 消息推送: 比赛结果通知推送 → after 首次安装App通知权限请求(0092, now shifted)
row = find_row(ws_ios, col5_key='通知时机-App在前台不推送')
if row:
    insert_tc(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: '功能',
        5: '比赛结果通知推送',
        6: '比赛场数据上传后推送比赛结果通知且点击跳转正确',
        7: '用户已授权通知权限，App不在前台',
        8: '1.比赛结束后收到推送通知\n2.检查通知标题和内容\n3.点击通知检查跳转目标',
        9: '1.收到标题“比赛结果通知”的APNs推送\n2.内容为“比赛结束，点击查看详情”\n3.跳转到场详情页→视频回放tab',
        10: 'P0',
    })
    print(f'  iOS R{row+1}: 比赛结果通知推送')

# iOS-3: 消息推送: 视频制作成功通知推送 → after 视频制作通知-局视频内容验证(0100)
row = find_row(ws_ios, col1_key='-0100')
if row:
    insert_tc(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: '功能',
        5: '视频制作成功通知推送',
        6: '视频制作完成后推送制作成功通知且点击跳转横屏播放',
        7: '用户已授权通知权限，App不在前台，有视频正在制作',
        8: '1.视频制作完成后收到推送通知\n2.检查通知标题和内容\n3.点击通知检查跳转',
        9: '1.收到标题“视频制作成功”的APNs推送\n2.内容格式正确（如“单杆XX分视频已制作完成，点击查看详情”）\n3.跳转到我的视频页面并打开视频横屏播放',
        10: 'P0',
    })
    print(f'  iOS R{row+1}: 视频制作成功通知推送')

# iOS-4: 分享模块: 成品视频分享到朋友圈 → after 视频分享到微信好友(0076)
row = find_row(ws_ios, col1_key='-0076')
if row:
    insert_tc(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '分享模块',
        4: '功能',
        5: '成品视频分享到微信朋友圈',
        6: '制作完成的视频通过微信SDK分享到朋友圈',
        7: '用户已登录App，有制作完成的视频，已安装微信',
        8: '1.点击视频分享按钮\n2.选择“微信朋友圈”选项\n3.在微信动态编辑页发布',
        9: '1.弹出分享弹窗\n2.调用微信SDK跳转至朋友圈动态编辑页\n3.发布成功',
        10: 'P1',
    })
    print(f'  iOS R{row+1}: 成品视频分享到朋友圈')

# iOS-5: 分享模块: 个人数据长图保存至相册 → after 个人数据长图分享(0079)
row = find_row(ws_ios, col1_key='-0079')
if row:
    insert_tc(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '分享模块',
        4: '功能',
        5: '个人数据长图保存至相册',
        6: '我的数据页面长图保存至相册（含权限处理）',
        7: '用户已登录App',
        8: '1.点击我的数据页面“保存到相册”按钮\n2.首次操作时观察相册权限请求\n3.拒绝权限后再次点击保存\n4.同意权限后保存长图',
        9: '1.点击后触发保存\n2.系统弹出相册权限请求弹窗\n3.弹窗提示“无相册权限，请至设置中开启”\n4.toast提示“已保存至相册”',
        10: 'P1',
    })
    print(f'  iOS R{row+1}: 个人数据长图保存至相册')

# ============================================================
# STEP 5: Renumber all sheets
# ============================================================
print('\n=== STEP 5: 重新编号 ===')
cnt_and = renumber_sheet(ws_and)
cnt_ios = renumber_sheet(ws_ios)
print(f'  安卓: {cnt_and}个TC')
print(f'  iOS: {cnt_ios}个TC')

# ============================================================
# STEP 6: Save
# ============================================================
ts = datetime.now().strftime('%Y%m%d_%H%M')
dst = f'iter-v1.0.1-第二期/测试用例-{ts}.xlsx'
try:
    wb.save(dst)
    print(f'\n已保存: {dst}')
except PermissionError:
    ts2 = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = f'iter-v1.0.1-第二期/测试用例-{ts2}.xlsx'
    wb.save(dst)
    print(f'\nWPS锁定，已保存为: {dst}')

# ============================================================
# STEP 7: Verify
# ============================================================
print(f'\n{"="*60}')
print('验证')
print(f'{"="*60}')
wb2 = openpyxl.load_workbook(dst)
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    tc_count = 0
    for r in range(2, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        if a.startswith('斯诺克大师V1.0.1-'):
            tc_count += 1
    print(f'\n{sn}: {tc_count}个TC')

# Step/expected check
mismatch = 0
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    for r in range(2, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        if a.startswith('斯诺克大师V1.0.1-'):
            h = str(ws_v.cell(row=r, column=8).value or '')
            i_val = str(ws_v.cell(row=r, column=9).value or '')
            sc = len([s for s in h.split('\n') if s.strip()]) if h else 0
            ec = len([e for e in i_val.split('\n') if e.strip()]) if i_val else 0
            if sc != ec:
                mismatch += 1
                print(f'  MISMATCH: {sn} R{r} {a}: steps={sc} expected={ec}')
print(f'步骤/预期对应检查: {"全部通过" if mismatch==0 else f"{mismatch}处不匹配"}')

# Numbering check
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    ids = []
    for r in range(2, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        if a.startswith('斯诺克大师V1.0.1-'):
            ids.append(int(a.split('-')[-1]))
    expected = list(range(1, len(ids)+1))
    if ids == expected:
        print(f'{sn}: 编号 {ids[0]:04d}~{ids[-1]:04d} 连续 ✓')
    else:
        breaks = [i for i in range(len(ids)-1) if ids[i+1] != ids[i]+1]
        print(f'{sn}: 断号! {breaks}')

# Check for duplicate scenarios in iOS 遗留优化
print(f'\niOS 遗留优化 Section检查:')
ws_v = wb2['国内iOS']
in_sec = False
for r in range(1, ws_v.max_row + 1):
    a = str(ws_v.cell(row=r, column=1).value or '').strip()
    b = str(ws_v.cell(row=r, column=2).value or '').strip()
    if a and not b and not a.startswith('斯诺克大师V') and r > 1:
        if in_sec and '遗留优化' not in a:
            break
        if '遗留优化' in a:
            in_sec = True
            print(f'  Section header: R{r} {a}')
            continue
    if in_sec and a.startswith('斯诺克大师V1.0.1-'):
        d = str(ws_v.cell(row=r, column=4).value or '')
        e = str(ws_v.cell(row=r, column=5).value or '')
        print(f'  {a} | {d} | {e[:50]}')

# Check 0121/0122 deleted
for r in range(1, ws_v.max_row + 1):
    a = str(ws_v.cell(row=r, column=1).value or '').strip()
    e = str(ws_v.cell(row=r, column=5).value or '')
    if '视频券落地页' in e and a.startswith('斯诺克大师V'):
        print(f'  WARNING: 视频券落地页 still in legacy at R{r} {a}')
    if '解锁方式弹窗内容' in e and a.startswith('斯诺克大师V'):
        in_legacy = False
        for rr in range(r, 0, -1):
            aa = str(ws_v.cell(row=rr, column=1).value or '').strip()
            if '遗留优化' in aa:
                in_legacy = True
                break
            if aa.startswith('斯诺克大师V'):
                break
        if in_legacy:
            print(f'  WARNING: 解锁弹窗内容 still in legacy at R{r} {a}')

# Show new cases
print(f'\n新增用例检查:')
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    for r in range(2, ws_v.max_row + 1):
        e = str(ws_v.cell(row=r, column=5).value or '')
        if '前台不推送' in e or '点击跳转' in e or '朋友圈' in e or '长图保存' in e or '比赛结果通知推送' in e or '制作成功通知推送' in e:
            a = str(ws_v.cell(row=r, column=1).value or '')
            d = str(ws_v.cell(row=r, column=4).value or '')
            print(f'  {sn}: {a} | {d} | {e[:40]}')
