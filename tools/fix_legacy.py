# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from copy import copy
from datetime import datetime

src = 'iter-v1.0.1-第二期/测试用例-20260909_2317.xlsx'
wb = openpyxl.load_workbook(src)

def insert_row(ws, target_row):
    ws.insert_rows(target_row)
    for c in range(1, 11):
        ref = ws.cell(row=target_row + 1, column=c)
        cell = ws.cell(row=target_row, column=c)
        cell.font = copy(ref.font)
        cell.fill = copy(ref.fill)
        cell.border = copy(ref.border)
        cell.alignment = copy(ref.alignment)

def renumber_sheet(ws):
    prefix = '斯诺克大师V1.0.1-'
    counter = 1
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(row=r, column=1).value or '')
        if val.startswith(prefix):
            counter = max(counter, 1)
            break
    for r in range(2, ws.max_row + 1):
        val = str(ws.cell(row=r, column=1).value or '')
        if val.startswith(prefix) or val == 'PLACEHOLDER':
            ws.cell(row=r, column=1).value = f'{prefix}{counter:04d}'
            counter += 1

# ======================
# 安卓 Sheet
# ======================
ws = wb['安卓']

# Find section boundaries
section_start = None
section_end = None
for r in range(1, ws.max_row + 1):
    val = str(ws.cell(row=r, column=1).value or '').strip()
    if '遗留优化' in val and not val.startswith('斯诺克大师V'):
        section_start = r + 1  # First TC after section header
    if section_start and section_end is None:
        # End = next section header or end of sheet
        if r > section_start:
            a_val = str(ws.cell(row=r, column=1).value or '').strip()
            b_val = str(ws.cell(row=r, column=2).value or '').strip()
            if a_val and not b_val and not a_val.startswith('斯诺克大师V'):
                section_end = r
                break
if section_end is None:
    section_end = ws.max_row + 1

print(f'安卓 遗留优化 Section: R{section_start} ~ R{section_end-1}')

# Find specific TCs
row_0120 = None  # 重装App后视频卡片状态
row_0122 = None  # 字体自适应

for r in range(section_start, section_end):
    val = str(ws.cell(row=r, column=1).value or '')
    f_val = str(ws.cell(row=r, column=6).value or '')
    if '0120' in val:
        row_0120 = r
    if '0122' in val:
        row_0122 = r

print(f'  0120 at R{row_0120}')
print(f'  0122 at R{row_0122}')

# === Change 1: 安卓新增 倍速播放 ===
# Insert after 0123 (退出播放器仍有下载进度显示)
row_0123 = None
for r in range(section_start, section_end):
    f_val = str(ws.cell(row=r, column=6).value or '')
    if '退出播放器仍有下载进度' in f_val:
        row_0123 = r
        break

if row_0123:
    insert_row(ws, row_0123 + 1)
    ws.cell(row=row_0123 + 1, column=1).value = 'PLACEHOLDER'
    ws.cell(row=row_0123 + 1, column=2).value = '斯诺克大师国内APP'
    ws.cell(row=row_0123 + 1, column=3).value = '遗留优化需求'
    ws.cell(row=row_0123 + 1, column=4).value = '功能'
    ws.cell(row=row_0123 + 1, column=5).value = '工控机制作视频倍速播放(预览态)'
    ws.cell(row=row_0123 + 1, column=6).value = '工控机制作的视频支持倍速播放（预览态）'
    ws.cell(row=row_0123 + 1, column=7).value = '用户有工控机制作的成品视频'
    ws.cell(row=row_0123 + 1, column=8).value = '1.进入视频播放器播放工控机制作的视频\n2.点击倍速按钮\n3.选择倍速档位（如1.25x/1.5x/2x）\n4.观看播放效果'
    ws.cell(row=row_0123 + 1, column=9).value = '1.播放器正常播放工控机制作视频\n2.弹出倍速选项\n3.选中倍速后视频按所选倍速播放\n4.倍速播放时视频处于预览态'
    ws.cell(row=row_0123 + 1, column=10).value = 'P1'
    print(f'  安卓: R{row_0123+1} 新增倍速播放')

# === Change 2: 优化 0120 缓存清除场景 ===
if row_0120:
    ws.cell(row=row_0120, column=5).value = '重装App/换手机/清除缓存后视频卡片状态为本地文件被删除'
    ws.cell(row=row_0120, column=6).value = '每次重装app/换手机/本地视频缓存被清除后视频卡片状态显示本地文件被删除（非制作中断状态）'
    ws.cell(row=row_0120, column=7).value = '用户已解锁视频且本地有视频文件'
    ws.cell(row=row_0120, column=8).value = '1.卸载App后重新安装并登录，查看视频卡片状态\n2.换手机登录同一账号，查看视频卡片状态\n3.在App设置中清除本地视频缓存，查看视频卡片状态'
    ws.cell(row=row_0120, column=9).value = '1.重装后视频卡片状态显示"本地文件被删除"（非制作中断状态）\n2.换手机后视频卡片状态显示"本地文件被删除"\n3.清除缓存后视频卡片状态显示"本地文件被删除"'
    print(f'  安卓: 优化0120 增加换手机/清除缓存场景')

# === Change 3: 优化 0122 字体自适应 ===
if row_0122:
    ws.cell(row=row_0122, column=5).value = '页面字体大小自适应及小字号页面优化'
    ws.cell(row=row_0122, column=6).value = 'App页面字体大小自适应不同屏幕，小字号页面字号已调整'
    ws.cell(row=row_0122, column=7).value = '有不同屏幕尺寸的设备（小屏/大屏）'
    ws.cell(row=row_0122, column=8).value = '1.在小屏设备上打开App，浏览视频卡片/播放器/个人数据等主要页面\n2.在大屏设备上打开App，浏览相同页面\n3.检查PRD中标注的小字号页面字体是否已调整\n4.检查全局自适应异常页面是否使用固定字号'
    ws.cell(row=row_0122, column=9).value = '1.小屏各页面字体自适应，无截断/重叠\n2.大屏各页面字体自适应，显示正常\n3.小字号页面字体已调整至可读\n4.自适应异常页面已使用固定字号'
    print(f'  安卓: 优化0122 细化到具体页面和小字号问题')

# ======================
# iOS Sheet
# ======================
ws_ios = wb['国内iOS']

section_start_ios = None
section_end_ios = None
for r in range(1, ws_ios.max_row + 1):
    val = str(ws_ios.cell(row=r, column=1).value or '').strip()
    if '遗留优化' in val and not val.startswith('斯诺克大师V'):
        section_start_ios = r + 1
    if section_start_ios and section_end_ios is None:
        if r > section_start_ios:
            a_val = str(ws_ios.cell(row=r, column=1).value or '').strip()
            b_val = str(ws_ios.cell(row=r, column=2).value or '').strip()
            if a_val and not b_val and not a_val.startswith('斯诺克大师V'):
                section_end_ios = r
                break
if section_end_ios is None:
    section_end_ios = ws_ios.max_row + 1

print(f'\niOS 遗留优化 Section: R{section_start_ios} ~ R{section_end_ios-1}')

# Find 0107 (无头像 - to insert font adaptation after it)
row_ios_0107 = None
row_ios_0108 = None  # 倍速播放
for r in range(section_start_ios, section_end_ios):
    val = str(ws_ios.cell(row=r, column=1).value or '')
    f_val = str(ws_ios.cell(row=r, column=6).value or '')
    if '0107' in val:
        row_ios_0107 = r
    if '0108' in val:
        row_ios_0108 = r

print(f'  0107 at R{row_ios_0107}')
print(f'  0108 at R{row_ios_0108}')

# === Change 4: iOS新增 字体自适应 ===
if row_ios_0108:
    insert_row(ws_ios, row_ios_0108 + 1)
    ws_ios.cell(row=row_ios_0108 + 1, column=1).value = 'PLACEHOLDER'
    ws_ios.cell(row=row_ios_0108 + 1, column=2).value = '斯诺克大师国内APP'
    ws_ios.cell(row=row_ios_0108 + 1, column=3).value = '遗留优化需求'
    ws_ios.cell(row=row_ios_0108 + 1, column=4).value = '功能'
    ws_ios.cell(row=row_ios_0108 + 1, column=5).value = '页面字体大小自适应及小字号页面优化'
    ws_ios.cell(row=row_ios_0108 + 1, column=6).value = 'App页面字体大小自适应不同iPhone屏幕，小字号页面字号已调整'
    ws_ios.cell(row=row_ios_0108 + 1, column=7).value = '有不同尺寸iPhone设备（小屏iPhone/iPhone Pro Max）'
    ws_ios.cell(row=row_ios_0108 + 1, column=8).value = '1.在小屏iPhone上打开App，浏览视频卡片/播放器/个人数据等主要页面\n2.在iPhone Pro Max上打开App，浏览相同页面\n3.检查PRD中标注的小字号页面字体是否已调整\n4.检查全局自适应异常页面是否使用固定字号'
    ws_ios.cell(row=row_ios_0108 + 1, column=9).value = '1.小屏iPhone各页面字体自适应，无截断/重叠\n2.Pro Max各页面字体自适应，显示正常\n3.小字号页面字体已调整至可读\n4.自适应异常页面已使用固定字号'
    ws_ios.cell(row=row_ios_0108 + 1, column=10).value = 'P2'
    print(f'  iOS: R{row_ios_0108+1} 新增字体自适应')

# Renumber both sheets
print('\n=== 重新编号 ===')
renumber_sheet(ws)
renumber_sheet(ws_ios)
print('  安卓编号完成')
print('  iOS编号完成')

# Save
ts = datetime.now().strftime('%Y%m%d_%H%M')
dst = f'iter-v1.0.1-第二期/测试用例-{ts}.xlsx'
try:
    wb.save(dst)
    print(f'\n已保存: {dst}')
except PermissionError:
    ts2 = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = f'iter-v1.0.1-第二期/测试用例-{ts2}.xlsx'
    wb.save(dst)
    print(f'\n已保存: {dst}')

# Final verification
wb2 = openpyxl.load_workbook(dst)
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    print(f'\n{sn} Section验证:')
    in_sec = False
    for r in range(1, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        b = str(ws_v.cell(row=r, column=2).value or '').strip()
        if a and not b and not a.startswith('斯诺克大师V') and not a.startswith('SM-') and r > 1:
            if in_sec and '遗留优化' not in a:
                break
            if '遗留优化' in a:
                in_sec = True
                continue
        if in_sec and a.startswith('斯诺克大师V'):
            f = str(ws_v.cell(row=r, column=6).value or '')[:60]
            j = str(ws_v.cell(row=r, column=10).value or '')
            print(f'  {a} | P{j} | {f}')

# Step/expected check
mismatch = 0
for sn in ['安卓', '国内iOS']:
    ws_v = wb2[sn]
    in_sec = False
    for r in range(1, ws_v.max_row + 1):
        a = str(ws_v.cell(row=r, column=1).value or '').strip()
        b = str(ws_v.cell(row=r, column=2).value or '').strip()
        if a and not b and not a.startswith('斯诺克大师V') and not a.startswith('SM-') and r > 1:
            if in_sec and '遗留优化' not in a:
                break
            if '遗留优化' in a:
                in_sec = True
                continue
        if in_sec and a.startswith('斯诺克大师V'):
            h = str(ws_v.cell(row=r, column=8).value or '')
            i = str(ws_v.cell(row=r, column=9).value or '')
            sc = len([s for s in h.split('\n') if s.strip()]) if h else 0
            ec = len([e for e in i.split('\n') if e.strip()]) if i else 0
            if sc != ec:
                mismatch += 1
                print(f'  MISMATCH: {sn} R{r} {a}: s={sc} e={ec}')

print(f'\n步骤/预期不对应: {mismatch}处')
