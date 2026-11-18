"""보고서형 WBS v3.2 Excel: v3.1 통합 문서를 복사해 WBS 시트에 두 열(GitHub 최초 커밋, 비고)을 더한다.

v3.1의 날짜·상태·수식·조건부 서식·간트 수식은 건드리지 않는다. 바뀌는 칸은 아래에서 직접 쓰는 칸뿐이며,
끝에서 v3.1과 칸 단위로 비교해 그 밖의 변경이 없는지 확인한다.
"""
from copy import copy
from pathlib import Path
import json
from openpyxl import load_workbook
from openpyxl.workbook.properties import CalcProperties

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'outputs/wbs-20261112/Revealed_WBS_v3.1_보고서형.xlsx'
OUT = ROOT / 'outputs/wbs-20261112/Revealed_WBS_v3.2_보고서형.xlsx'
D = json.loads((HERE / 'wbs-v3.2.json').read_text(encoding='utf-8'))
HEADER_ROW, FIRST_ROW, LAST_ROW = 7, 8, 28
EVIDENCE_COL, NOTE_COL = 12, 13  # L, M


def styled(ws, row, col, value, like):
    """like 칸의 서식을 복사해 값을 쓴다."""
    cell = ws.cell(row=row, column=col, value=value)
    cell._style = copy(like._style)
    return cell


def wrap(cell):
    alignment = copy(cell.alignment)
    alignment.wrap_text = True
    alignment.vertical = 'center'
    cell.alignment = alignment


def build():
    wb = load_workbook(SOURCE)
    changed = set()  # (시트 이름, 칸 주소)

    ws = wb['WBS']
    ws['A4'] = ('중간보고서 표 형식 · 5개 단계 / 16개 주요 작업 · 문서 2026.11.13 / 상태 11.12 기준 · '
                f'코드 기준 microstone {D["code_basis"][:7]} · v3.2')
    changed.add(('WBS', 'A4'))
    for col, title in ((EVIDENCE_COL, 'GitHub 최초 커밋'), (NOTE_COL, '비고(남은 일)')):
        changed.add(('WBS', styled(ws, HEADER_ROW, col, title, ws.cell(row=HEADER_ROW, column=11)).coordinate))
    tasks = {t['id']: t for t in D['tasks']}
    groups = {g['id']: g for g in D['groups']}
    seen = set()
    for row in range(FIRST_ROW, LAST_ROW + 1):
        code = str(ws.cell(row=row, column=1).value)
        like = ws.cell(row=row, column=4)  # 작업명 칸의 글꼴·테두리·배경을 따른다
        if code in groups:
            ws.cell(row=row, column=5).value = groups[code]['uc_scope']
            changed.add(('WBS', ws.cell(row=row, column=5).coordinate))
            evidence, note = '-', None
        else:
            task = tasks[code]
            assert ws.cell(row=row, column=4).value == task['name'], code
            assert ws.cell(row=row, column=11).value == task['status'], code
            assert ws.cell(row=row, column=7).value.date().isoformat() == task['start'], code
            assert ws.cell(row=row, column=8).value.date().isoformat() == task['end'], code
            evidence = '\n'.join(f'{e["date"][5:]} {e["label"]}' for e in task['github_first']) or '-'
            note = task['note'] or '-'
        seen.add(code)
        for col, value in ((EVIDENCE_COL, evidence), (NOTE_COL, note)):
            cell = styled(ws, row, col, value, like)
            wrap(cell)
            changed.add(('WBS', cell.coordinate))
    assert seen == set(tasks) | set(groups), '시트의 행과 자료의 작업이 다름'
    ws.column_dimensions['L'].width = 20
    ws.column_dimensions['M'].width = 46
    for row, note in zip((37, 38), (D['notes'][1], D['notes'][4])):  # GitHub 최초 커밋, 비고 설명
        assert ws.cell(row=row, column=1).value is None
        changed.add(('WBS', styled(ws, row, 1, note, ws['A36']).coordinate))

    gantt = wb['간트차트']
    assert gantt['A27'].value is None
    styled(gantt, 27, 1, '실제 코드 반영 시점은 WBS 시트의 GitHub 최초 커밋 열과 PDF 간트차트의 ● 표식에 있습니다.', gantt['A26'])
    changed.add(('간트차트', 'A27'))

    wb.calculation = CalcProperties(fullCalcOnLoad=True)  # 저장된 계산값이 없으므로 열 때 다시 계산하게 한다
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)

    # v3.1과 칸 단위 비교: 위에서 쓴 칸 말고는 값·수식이 같아야 한다.
    before, after = load_workbook(SOURCE), load_workbook(OUT)
    assert before.sheetnames == after.sheetnames
    formulas = 0
    for name in before.sheetnames:
        a, b = before[name], after[name]
        for row in range(1, max(a.max_row, b.max_row) + 1):
            for col in range(1, max(a.max_column, b.max_column) + 1):
                old, new = a.cell(row=row, column=col).value, b.cell(row=row, column=col).value
                formulas += isinstance(new, str) and new.startswith('=')
                if old != new:
                    assert (name, b.cell(row=row, column=col).coordinate) in changed, (name, row, col, old, new)
        assert [str(m) for m in a.merged_cells.ranges] == [str(m) for m in b.merged_cells.ranges]
        assert len(a.conditional_formatting) == len(b.conditional_formatting)
        assert len(a.data_validations.dataValidation) == len(b.data_validations.dataValidation)
    print(OUT)
    print(f'{len(changed)} cells written; {formulas} formulas, merges, conditional formats and validations unchanged from v3.1.')


if __name__ == '__main__':
    build()
