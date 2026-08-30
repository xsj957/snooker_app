---
name: test-case-ops
description: 测试用例 Excel 操作工具。用于新增、删除、修改测试用例行，处理 insert_rows/delete_rows 合并单元格问题。
triggers:
  - 新增用例
  - 删除用例
  - 修改用例
  - 批量变更
  - insert_rows
  - delete_rows
  - 测试用例操作
  - 用例操作
---

# 测试用例 Excel 操作 Skill

## 使用场景

当用户要求对测试用例 Excel 进行**新增、删除、修改**操作时，加载本 skill 获取 Python 代码模板。

## 使用前必须确认

1. **读取项目 CLAUDE.md**，确认当前项目的编号前缀（如 `斯诺克大师V1.0.1-`）
2. **确认目标 Sheet**（安卓 / iOS / 冒烟测试）
3. **确认目标 Section**（用例应归属的功能模块）

## 核心代码模板

### 样式常量（所有操作复用）

> ⚠️ 以下值必须与全局 CLAUDE.md 中的测试用例规范保持一致。如全局规范变更，此处同步更新。

```python
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment

# --- TC 数据行样式 ---
TC_FONT = Font(name='微软雅黑', size=10)
TC_FILL = PatternFill(start_color='FFFCE4EC', end_color='FFFCE4EC', fill_type='solid')
TC_BORDER = Border(left=Side(style='thin'), right=Side(style='thin'),
                   top=Side(style='thin'), bottom=Side(style='thin'))

# 居中列（A, J, K~S）
CENTER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
# 左对齐列（F, G, H, I, T）
LEFT_ALIGN = Alignment(horizontal='left', vertical='center', wrap_text=True)

# --- Section Header 样式 ---
SECTION_FONT = Font(name='微软雅黑', size=10, bold=True, color='FFFFFFFF')
SECTION_FILL = PatternFill(start_color='FF2F5496', end_color='FF2F5496', fill_type='solid')

# --- 表头样式（第1行）---
HEADER_FONT = Font(name='微软雅黑', size=10, bold=True, color='FFFFFFFF')
HEADER_FILL = PatternFill(start_color='FF2F5496', end_color='FF2F5496', fill_type='solid')
```

### 工具函数（所有操作复用）

```python
def unmerge_all(ws):
    """取消所有合并单元格"""
    for m in list(ws.merged_cells.ranges):
        ws.merged_cells.ranges.remove(m)

def record_sections(ws):
    """操作前记录 Section Header 行号（A~J 合并的行）"""
    sections = []
    for m in ws.merged_cells.ranges:
        if m.min_col == 1 and m.max_col >= 10:  # A列起始，跨到J列或更远
            sections.append(m.min_row)
    return sorted(sections)

def rebuild_sections(ws, section_rows):
    """操作后在同样的行号重建 Section 合并"""
    for r in section_rows:
        if r <= ws.max_row:
            ws.merge_cells(f'A{r}:J{r}')
            ws.cell(r, 1).font = SECTION_FONT
            ws.cell(r, 1).fill = SECTION_FILL

def apply_tc_style(ws, row, left_align_cols=(6, 7, 8, 9, 20)):
    """给 TC 数据行应用样式。left_align_cols 为左对齐列号（F,G,H,I,T）"""
    for c in range(1, 21):  # A~T 共20列
        cell = ws.cell(row, c)
        cell.font = TC_FONT
        cell.fill = TC_FILL
        cell.border = TC_BORDER
        cell.alignment = LEFT_ALIGN if c in left_align_cols else CENTER_ALIGN

def renumber(ws, prefix):
    """重新编号：跳过 Section Header，对 TC 行按顺序编号"""
    c = 1
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        cell = row[0]
        val = cell.value
        # 匹配正式 TC 编号（如 斯诺克大师V1.0.1-0001）
        if val and str(val).startswith(prefix):
            cell.value = f"{prefix}{c:04d}"
            c += 1
        # 匹配空编号但有数据的行（insert_rows 产生的新行，B列有系统名）
        elif (val is None or str(val).strip() == '') and row[1].value:
            cell.value = f"{prefix}{c:04d}"
            cell.font = TC_FONT
            cell.fill = TC_FILL
            cell.border = TC_BORDER
            cell.alignment = CENTER_ALIGN
            c += 1

def validate(ws, prefix):
    """操作后验证：内容完整性 + 编号连续性"""
    errors = []
    prev_num = 0
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 1).value
        # 跳过 Section Header（合并行的首行）
        if ws.cell(r, 1).value and str(ws.cell(r, 1).value).startswith('【'):
            continue
        # 检查 TC 行
        if v and str(v).startswith(prefix):
            num = int(str(v).split('-')[-1])
            if num != prev_num + 1:
                errors.append(f"行{r}: 编号不连续，期望{prefix}{prev_num+1:04d}，实际{v}")
            prev_num = num
            # 关键列不能为空
            if not ws.cell(r, 2).value:  # B列：测试系统
                errors.append(f"行{r}: B列（测试系统）为空")
            if not ws.cell(r, 4).value:  # D列：测试类型
                errors.append(f"行{r}: D列（测试类型）为空")
            if not ws.cell(r, 6).value:  # F列：用例标题
                errors.append(f"行{r}: F列（用例标题）为空")
    if errors:
        raise Exception("验证失败:\n" + "\n".join(errors))
    print(f"[OK] 验证通过，共 {prev_num} 条用例")
```

### 新增用例（insert）

```python
def insert_tc(ws, insert_after_row, tc_data, prefix):
    """
    在 insert_after_row 之后插入一条新用例。

    Args:
        ws: 工作表对象
        insert_after_row: 在哪一行之后插入（Section 内某行之后）
        tc_data: 长度为20的列表，对应 A~T 列的值
        prefix: 编号前缀，如 '斯诺克大师V1.0.1-'
    """
    # 步骤1: 记录 Section 位置
    sections = record_sections(ws)

    # 步骤2: 取消所有合并
    unmerge_all(ws)

    # 步骤3: 插入空行
    new_row = insert_after_row + 1
    ws.insert_rows(new_row)

    # 步骤4: 填写数据
    for col, val in enumerate(tc_data, 1):
        ws.cell(new_row, col, val)

    # 步骤5: 应用样式
    apply_tc_style(ws, new_row)

    # 步骤6: 重新编号（从新行开始往后所有 TC 编号 +1）
    renumber(ws, prefix)

    # 步骤7: 重建 Section 合并
    # 注意：insert_rows 会让 Section 行号 +1（如果在 Section 之前插入）
    rebuilt_sections = []
    for s in sections:
        rebuilt_sections.append(s + 1 if s > insert_after_row else s)
    rebuild_sections(ws, rebuilt_sections)

    # 步骤8: 验证
    validate(ws, prefix)
```

### 删除用例（delete）

```python
def delete_tc(ws, delete_row, prefix):
    """
    删除指定行的用例。

    Args:
        ws: 工作表对象
        delete_row: 要删除的行号
        prefix: 编号前缀
    """
    # 步骤1: 记录 Section 位置
    sections = record_sections(ws)

    # 步骤2: 取消所有合并
    unmerge_all(ws)

    # 步骤3: 删除目标行
    ws.delete_rows(delete_row)

    # 步骤4: 重新编号（后续 TC 编号 -1）
    renumber(ws, prefix)

    # 步骤5: 重建 Section 合并
    # 注意：delete_rows 会让 Section 行号 -1（如果在 Section 之后删除）
    rebuilt_sections = []
    for s in sections:
        rebuilt_sections.append(s - 1 if s > delete_row else s)
    rebuilt_sections = [s for s in rebuilt_sections if s >= 2]  # 过滤无效行号
    rebuild_sections(ws, rebuilt_sections)

    # 步骤6: 验证
    validate(ws, prefix)
```

### 修改用例（update）

```python
def update_tc(ws, row, col_updates, prefix):
    """
    修改指定行的部分列。

    Args:
        ws: 工作表对象
        row: 目标行号
        col_updates: {列号: 新值} 字典，如 {6: "新标题", 9: "P0"}
        prefix: 编号前缀（用于验证）
    """
    for col, val in col_updates.items():
        ws.cell(row, col, val)
    # 修改不需要重新编号，只需验证
    validate(ws, prefix)
```

## 批量变更操作顺序

1. **先删除** → 调用 `delete_tc()`，每次删除后重新编号
2. **再修改** → 调用 `update_tc()`
3. **最后新增** → 调用 `insert_tc()`，每条新增后重新编号

> ⚠️ 多条删除时，**从后往前删**（行号大的先删），避免前面的删除影响后面的行号。

## 保存文件

```python
from datetime import datetime

timestamp = datetime.now().strftime('%Y%m%d_%H%M')
dst = f'测试用例-{timestamp}.xlsx'
wb.save(dst)
print(f"[OK] Saved: {dst}")
```

## 关键验证点（每次操作后自动检查）

- [ ] 新行无合并单元格
- [ ] 后续行内容完整（测试系统、测试类型、用例标题不为空）
- [ ] Section Header 合并正确
- [ ] 编号连续无断号
- [ ] 样式与已有行一致
