# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from copy import copy
from datetime import datetime

src = 'iter-v1.0.1-第二期/测试用例-20260909_2328.xlsx'
wb = openpyxl.load_workbook(src)

def insert_ui_row(ws, after_row, tc_data):
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

def renumber_sheet(ws):
    prefix = '斯诺克大师V1.0.1-'
    counter = 1
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(row=r, column=1).value or '')
        if val.startswith(prefix) or val == 'PLACEHOLDER':
            ws.cell(row=r, column=1).value = f'{prefix}{counter:04d}'
            counter += 1
    return counter - 1

def find_row(ws, key_col1=None, key_col6=None):
    for r in range(2, ws.max_row + 1):
        a = str(ws.cell(row=r, column=1).value or '')
        f = str(ws.cell(row=r, column=6).value or '')
        if key_col1 and key_col1 in a:
            return r
        if key_col6 and key_col6 in f:
            return r
    return None

# ======================
# Android Sheet - 6 UI cases
# ======================
ws = wb['安卓']
print('=== 安卓 Sheet ===')

# 1. 支付模块: 我的卡券页面UI → after 0011
row = find_row(ws, key_col1='-0011')
if row:
    insert_ui_row(ws, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '支付模块',
        4: 'UI',
        5: '我的卡券页面展示',
        6: '我的卡券页面UI符合设计稿，Bundle卡和Reward Coupon卡样式正确',
        7: '用户已购买视频券套餐',
        8: '1.进入我的→视频券购买banner→购买任意套餐\n2.购买成功后进入我的卡券页面\n3.检查Bundle卡UI样式（含有效期和券数量文案）\n4.检查Reward Coupon卡UI样式（含有效期和单张券文案）',
        9: '1.购买成功，跳转至我的卡券页面\n2.页面展示正确\n3.Bundle卡红色主题，显示"Can be used to unlock X wonderful video"及有效期\n4.Reward Coupon卡显示"Can be used to unlock 1 wonderful video"及有效期',
        10: 'P2',
    })
    print(f'  R{row+1}: 我的卡券页面UI')

# 2. 个人数据: 个人数据页整体布局UI → after 0062
row = find_row(ws, key_col1='-0062')
if row:
    insert_ui_row(ws, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '个人数据模块',
        4: 'UI',
        5: '个人数据页整体布局',
        6: '新版个人数据页整体布局符合UI设计稿，各区域排列和间距正确',
        7: '用户有完整的个人数据（有评级、有比赛记录）',
        8: '1.进入我的数据页面\n2.检查顶部个人卡片（头像+姓名+评级标签+四项数据）\n3.检查Tab切换栏+时间筛选器UI\n4.从上到下检查：基础数据行→当前评级卡片→胜率/时长行→进球成功率卡片→各类成功率进度条→稳定性区域→单杆高分卡片',
        9: '1.页面正常加载，布局与设计稿一致\n2.个人卡片样式正确，评级标签蓝色\n3.Tab栏和时间筛选器样式正确\n4.各区域排列顺序、间距、样式均符合UI设计稿',
        10: 'P1',
    })
    print(f'  R{row+1}: 个人数据页整体布局UI')

# 3. 个人数据: 数据可视化组件UI → after 称号展示
row = find_row(ws, key_col6='称号')
if row:
    insert_ui_row(ws, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '个人数据模块',
        4: 'UI',
        5: '数据可视化组件UI',
        6: '评级能力图谱雷达图、各类成功率进度条（平均与最佳）、单杆高分卡片分栏UI符合设计稿',
        7: '用户有评级和完整比赛数据',
        8: '1.查看当前评级卡片中的五维雷达图（进攻/防守/心态/长台/围球）\n2.查看红球/彩球/长台/走位/架杆成功率的平均与最佳进度条\n3.查看单杆高分卡片分栏布局（20+/30+/40+/50+/80+/100+）',
        9: '1.五维雷达图蓝色填充，五个维度标签正确显示\n2.每项成功率左侧蓝色进度条+右侧百分比数值，平均与最佳分别展示\n3.单杆高分卡片蓝色背景，分栏排列正确',
        10: 'P2',
    })
    print(f'  R{row+1}: 数据可视化组件UI')

# 4. 分享模块: 长图分享弹窗UI → after 0089
row = find_row(ws, key_col1='-0089')
if row:
    insert_ui_row(ws, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '分享模块',
        4: 'UI',
        5: '个人数据长图分享弹窗样式',
        6: '个人数据页长图分享弹窗UI符合设计稿，仅显示微信/朋友圈/保存到相册3个选项（无抖音）',
        7: '用户在个人数据页点击分享按钮',
        8: '1.点击我的数据页面分享按钮\n2.检查弹窗背景（半透明蒙层+长图缩略）\n3.检查3个分享选项图标和文案\n4.对比成品视频分享弹窗（4个选项含抖音）确认差异',
        9: '1.底部弹出分享弹窗\n2.背景为半透明蒙层+个人数据页长图缩略\n3.微信（绿色）、微信朋友圈（绿色）、保存到相册（灰色）3个圆形图标\n4.长图分享弹窗无抖音选项，与视频分享弹窗明显区分',
        10: 'P2',
    })
    print(f'  R{row+1}: 长图分享弹窗UI')

# 5. 消息推送: 通知权限请求弹窗UI → after 0106
row = find_row(ws, key_col1='-0106')
if row:
    insert_ui_row(ws, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: 'UI',
        5: '通知权限请求弹窗样式',
        6: '首次安装App时通知权限请求弹窗UI符合设计稿，文案和按钮样式正确',
        7: '用户首次安装App并打开（非覆盖安装/升级安装）',
        8: '1.首次安装并打开App\n2.观察通知权限请求弹窗样式\n3.检查弹窗文案和按钮\n4.点击拒绝后再次打开App检查是否再次弹出',
        9: '1.弹出系统通知权限请求弹窗\n2.弹窗显示“允许发送通知？”\n3.有“拒绝”和“始终允许”两个按钮\n4.拒绝后再次打开不再弹出系统弹窗（可在App内引导开启）',
        10: 'P2',
    })
    print(f'  R{row+1}: 通知权限请求弹窗UI')

# Renumber Android
cnt_and = renumber_sheet(ws)
print(f'  安卓: {cnt_and}个TC')

# ======================
# iOS Sheet - 7 UI cases
# ======================
ws_ios = wb['国内iOS']
print(f'\n=== 国内iOS Sheet ===')

# 1. 支付模块: 我的卡券页面UI → after 0012
row = find_row(ws_ios, key_col1='-0012')
if row:
    insert_ui_row(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '支付模块',
        4: 'UI',
        5: '我的卡券页面展示',
        6: '我的卡券页面UI符合设计稿，Bundle卡和Reward Coupon卡样式正确',
        7: '用户已通过IAP购买视频券套餐',
        8: '1.IAP购买任意套餐成功后进入我的卡券页面\n2.检查Bundle卡UI样式（含有效期和券数量文案）\n3.检查Reward Coupon卡UI样式（含有效期和单张券文案）',
        9: '1.页面展示正确\n2.Bundle卡红色主题，显示"Can be used to unlock X wonderful video"及有效期\n3.Reward Coupon卡显示"Can be used to unlock 1 wonderful video"及有效期',
        10: 'P2',
    })
    print(f'  R{row+1}: 我的卡券页面UI')

# 2. 支付模块: iOS退款介绍页UI → after 解锁方式弹窗内容验证
row = find_row(ws_ios, key_col6='解锁方式弹窗内容')
if row:
    insert_ui_row(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '支付模块',
        4: 'UI',
        5: '退款方式介绍页展示',
        6: 'iOS端退款方式介绍静态页面UI符合设计稿，退款建议按视频状态正确展示',
        7: '用户有已解锁的视频且视频状态为下载失败/制作失败',
        8: '1.点击下载失败/制作失败视频卡片上的退款按钮\n2.进入退款方式介绍静态页面\n3.检查页面整体布局和设计稿一致性\n4.检查工控机制作视频和本地制作视频的退款建议展示',
        9: '1.进入退款方式介绍静态页面\n2.页面布局与new_p24_img00设计稿一致\n3.工控机制作视频按72h规则显示退款建议\n4.App本地制作视频按失败状态显示退款建议',
        10: 'P2',
    })
    print(f'  R{row+1}: iOS退款介绍页UI')

# 3. 个人数据: 个人数据页整体布局UI → after 0055
row = find_row(ws_ios, key_col1='-0055')
if row:
    insert_ui_row(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '个人数据模块',
        4: 'UI',
        5: '个人数据页整体布局',
        6: '新版个人数据页整体布局符合UI设计稿，各区域排列和间距正确',
        7: '用户有完整的个人数据（有评级、有比赛记录）',
        8: '1.进入我的数据页面\n2.检查顶部个人卡片（头像+姓名+评级标签+四项数据）\n3.检查Tab切换栏+时间筛选器UI\n4.从上到下检查各数据区域排列',
        9: '1.页面正常加载，布局与设计稿一致\n2.个人卡片样式正确\n3.Tab栏和时间筛选器样式正确\n4.各区域排列顺序、间距、样式均符合UI设计稿',
        10: 'P1',
    })
    print(f'  R{row+1}: 个人数据页整体布局UI')

# 4. 个人数据: 数据可视化组件UI → after 称号展示
row = find_row(ws_ios, key_col6='称号')
if row:
    insert_ui_row(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '个人数据模块',
        4: 'UI',
        5: '数据可视化组件UI',
        6: '评级能力图谱雷达图、各类成功率进度条（平均与最佳）、单杆高分卡片分栏UI符合设计稿',
        7: '用户有评级和完整比赛数据',
        8: '1.查看当前评级卡片中的五维雷达图\n2.查看各类成功率平均与最佳进度条\n3.查看单杆高分卡片分栏布局',
        9: '1.五维雷达图蓝色填充，五个维度标签正确\n2.每项成功率左侧蓝色进度条+右侧数值，平均与最佳分别展示\n3.单杆高分卡片蓝色背景，分栏排列正确',
        10: 'P2',
    })
    print(f'  R{row+1}: 数据可视化组件UI')

# 5. 分享模块: 长图分享弹窗UI → after 0079
row = find_row(ws_ios, key_col1='-0079')
if row:
    insert_ui_row(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '分享模块',
        4: 'UI',
        5: '个人数据长图分享弹窗样式',
        6: '个人数据页长图分享弹窗UI符合设计稿，仅显示微信/朋友圈/保存到相册3个选项（无抖音）',
        7: '用户在个人数据页点击分享按钮',
        8: '1.点击我的数据页面分享按钮\n2.检查弹窗背景和长图缩略\n3.检查3个分享选项图标和文案\n4.对比成品视频分享弹窗确认差异',
        9: '1.底部弹出分享弹窗\n2.背景为半透明蒙层+长图缩略\n3.微信（绿色）、微信朋友圈（绿色）、保存到相册（灰色）3个选项\n4.无抖音选项，与视频分享弹窗区分',
        10: 'P2',
    })
    print(f'  R{row+1}: 长图分享弹窗UI')

# 6. 消息推送: 通知权限请求弹窗UI → after 0101
row = find_row(ws_ios, key_col1='-0101')
if row:
    insert_ui_row(ws_ios, row, {
        1: 'PLACEHOLDER',
        2: '斯诺克大师国内APP',
        3: '消息推送模块',
        4: 'UI',
        5: '通知权限请求弹窗样式',
        6: '首次安装App时iOS系统通知权限请求弹窗UI符合设计稿',
        7: '用户首次安装App并打开',
        8: '1.首次安装并打开App\n2.观察iOS系统通知权限请求弹窗样式\n3.检查弹窗文案和按钮',
        9: '1.弹出iOS系统通知权限请求弹窗\n2.弹窗样式符合p26_img00设计稿\n3.有“不允许”和“允许”两个按钮',
        10: 'P2',
    })
    print(f'  R{row+1}: 通知权限请求弹窗UI')

# Renumber iOS
cnt_ios = renumber_sheet(ws_ios)
print(f'  iOS: {cnt_ios}个TC')

# ======================
# Save
# ======================
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

# ======================
# Final verification
# ======================
print(f'\n{"="*60}')
print('验证')
print(f'{"="*60}')
wb2 = openpyxl.load_workbook(dst)
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    tc_count = 0
    ui_count = 0
    ui_list = []
    for r in range(2, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        d = str(ws_v.cell(row=r, column=4).value or '').strip()
        e = str(ws_v.cell(row=r, column=5).value or '').strip()
        f = str(ws_v.cell(row=r, column=6).value or '').strip()
        if a.startswith('斯诺克大师V1.0.1-'):
            tc_count += 1
            if d == 'UI':
                ui_count += 1
                ui_list.append(f'{a} | {e[:35]} | {f[:50]}')
    print(f'\n{sn}: {tc_count}个TC, UI {ui_count}个 ({ui_count*100//tc_count}%)')
    for u in ui_list:
        print(f'  \U0001f3a8 {u}')

# Step/expected mismatch check
mismatch = 0
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    for r in range(2, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        if a.startswith('斯诺克大师V1.0.1-'):
            h = str(ws_v.cell(row=r, column=8).value or '')
            i = str(ws_v.cell(row=r, column=9).value or '')
            sc = len([s for s in h.split('\n') if s.strip()]) if h else 0
            ec = len([e for e in i.split('\n') if e.strip()]) if i else 0
            if sc != ec:
                mismatch += 1
                print(f'  MISMATCH: {sn} R{r} {a}: steps={sc} expected={ec}')
print(f'\n步骤/预期对应检查: {"全部通过" if mismatch==0 else f"{mismatch}处不匹配"}')

# Check sequential numbering
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
