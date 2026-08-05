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

## 核心代码模板

### 样式常量（所有操作复用）

```python
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment

TC_FONT = Font(name='微软雅黑', size=10)
TC_FILL = PatternFill(start_color='FFFCE4EC', end_color='FFFCE4EC', fill_type='solid')
TC_BORDER = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
TC_ALIGN = Alignment(vertical='center', wrap_text=True)

SECTION_FONT = Font(name='微软雅黑', size=10, bold=True, color='FFFFFFFF')
SECTION_FILL = PatternFill(start_color='FF2F5496', end_color='FF2F5496', fill_type='solid')

HEADER_FONT = Font(name='微软雅黑', size=10, bold=True, color='FFFFFFFF')
HEADER_FILL = PatternFill(start_color='FF2F5496', end_color='FF2F5496', fill_type='solid')
HEADER_ALIGN = Alignment(horizontal='center', vertical='center')
```

### 修复版 insert_rows（新增用例）

**关键修复**：操作前先取消所有合并，操作后在新位置重新合并。

```python
def fixed_insert_rows(ws, insert_row, new_tc_data):
    # 步骤1: 取消所有 Section 合并
    for m in list(ws.merged_cells.ranges):
        ws.merged_cells.ranges.remove(m)

    # 步骤2: 执行 insert_rows
    ws.insert_rows(insert_row + 1)
    new_row = insert_row + 1

    # 步骤3: 填写新用例（除执行结果/备注外不能为空）
    for col, val in enumerate(new_tc_data, 1):
        ws.cell(new_row, col, val)
    for c in range(1, 11):
        ws.cell(new_row, c).font = TC_FONT
        ws.cell(new_row, c).fill = TC_FILL
        ws.cell(new_row, c).border = TC_BORDER
        ws.cell(new_row, c).alignment = Alignment(vertical='center', wrap_text=True)

    # 步骤4: 后续编号 +1
    for r in range(insert_row + 2, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).startswith('TC-'):
            num = int(str(v).split('-')[1])
            ws.cell(r, 1).value = f'TC-{num+1:03d}'

    # 步骤5: 重新合并所有 Section
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).startswith('【'):
            ws.merge_cells(f'A{r}:J{r}')
            ws.cell(r, 1).font = SECTION_FONT
            ws.cell(r, 1).fill = SECTION_FILL

    # 步骤6: 验证内容完整性
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).startswith('TC-'):
            if not ws.cell(r, 2).value or not ws.cell(r, 4).value:
                raise Exception(f"内容丢失！行 {r}")
```

### 修复版 delete_rows（删除用例）

```python
def fixed_delete_rows(ws, delete_row):
    # 步骤1: 取消所有 Section 合并
    for m in list(ws.merged_cells.ranges):
        ws.merged_cells.ranges.remove(m)

    # 步骤2: 删除目标行
    ws.delete_rows(delete_row)

    # 步骤3: 后续编号 -1
    for r in range(delete_row, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).startswith('TC-'):
            num = int(str(v).split('-')[1])
            ws.cell(r, 1).value = f'TC-{num-1:03d}'

    # 步骤4: 重新合并所有 Section
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).startswith('【'):
            ws.merge_cells(f'A{r}:J{r}')
            ws.cell(r, 1).font = SECTION_FONT
            ws.cell(r, 1).fill = SECTION_FILL

    # 步骤5: 验证内容完整性
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).startswith('TC-'):
            if not ws.cell(r, 2).value or not ws.cell(r, 4).value:
                raise Exception(f"内容丢失！行 {r}")
```

## 批量变更操作顺序

1. **先删除** → 重新编号
2. **再修改** → 调整内容
3. **最后新增** → 插入并重新编号

## 保存文件注意事项

```python
try:
    wb.save('测试用例.xlsx')
except PermissionError:
    wb.save('测试用例_temp.xlsx')
    print('原文件被 WPS 占用，已保存为 测试用例_temp.xlsx')
```

## 关键验证点（每次操作后必须检查）

- [ ] 新行无合并单元格
- [ ] 后续行内容完整（场景、标题不为空）
- [ ] Section Header 合并正确
- [ ] 编号连续无断号
- [ ] 样式与已有行一致
