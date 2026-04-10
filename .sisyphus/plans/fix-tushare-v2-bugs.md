# Fix Tushare V2 Downloader Bugs

## TL;DR

> **Quick Summary**: Fix 3 bugs in `fetcher_daily_price_tushare_v2.py`: datetime inconsistency, missing daily_basic stats tracking, and incomplete resume logic.
>
> **Deliverables**: Fixed `fetcher_daily_price_tushare_v2.py` with all 3 bugs resolved
> - [x] Bug 1: Datetime format consistency in `calculate_qfq`
> - [x] Bug 2: daily_basic record counting in `download_date_range`
> - [x] Bug 3: Resume logic checks multiple tables
>
> **Estimated Effort**: Quick (< 10 minutes)
> **Parallel Execution**: NO - Sequential single-file fix
> **Critical Path**: Bug 1 → Bug 2 → Bug 3

---

## Context

### Original Request
用户要求修复 `fetcher_daily_price_tushare_v2.py` 中发现的所有bug。

### Interview Summary
**Key Discussions**:
- Identified 3 bugs in the tushare downloader
- All bugs need to be fixed in one file

**Research Findings**:
- Bug 1 (Line 185): `calculate_qfq` converts trade_date to datetime, but `save_daily_price_qfq` line 408 expects string format
- Bug 2 (Lines 515-570): `download_date_range` doesn't track daily_basic record counts
- Bug 3 (Line 489): Resume logic only checks `adj_factor_tushare` table

---

## Work Objectives

### Core Objective
Fix all 3 identified bugs in `fetcher_daily_price_tushare_v2.py` to ensure:
1. Datetime format consistency throughout the data pipeline
2. Accurate statistics tracking for daily_basic downloads
3. Robust resume logic that checks multiple tables

### Concrete Deliverables
- Fixed `data/updaters/fetcher_daily_price_tushare_v2.py`

### Definition of Done
- [ ] Line 185: `calculate_qfq` converts trade_date to string format `%Y-%m-%d`
- [ ] Lines 519+: `daily_basic_records` counter added and tracked
- [ ] Line 562+: `total_daily_basic_records` added to result dict
- [ ] Line 489+: Resume logic checks `daily_price_raw` table too

### Must Have
- Datetime strings in consistent `%Y-%m-%d` format
- daily_basic record count tracked in statistics
- Resume logic works with both adj_factor and daily_price_raw tables

### Must NOT Have (Guardrails)
- No changes to function signatures
- No changes to database schema
- No changes to CLI interface

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (no formal test framework)
- **Automated tests**: None
- **Framework**: N/A

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/`.

- **Verification Method**: Code review + syntax check
  - Read the modified file to verify each fix
  - Run `python -c "import data.updaters.fetcher_daily_price_tushare_v2"` to verify no syntax errors

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Sequential - single file):
├── Bug 1: Fix datetime format in calculate_qfq (line 185)
├── Bug 2: Add daily_basic stats tracking (lines 519, 551, 562-569)
└── Bug 3: Fix resume logic (line 489)

Wave FINAL (Verification):
└── Task F1: Code review + syntax verification
```

---

## TODOs

- [ ] 1. Fix Bug 1: Datetime format in calculate_qfq

  **What to do**:
  - Find line 185 in `calculate_qfq` function
  - Change `df['trade_date'] = pd.to_datetime(df['trade_date'])`
  - To `df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')`

  **Must NOT do**:
  - Do not change any other lines in the function

  **References**:
  - `data/updaters/fetcher_daily_price_tushare_v2.py:185` - Current datetime conversion
  - `data/updaters/fetcher_daily_price_tushare_v2.py:408` - Shows expected string format pattern

  **Acceptance Criteria**:
  - [ ] Line 185 produces `%Y-%m-%d` string format
  - [ ] No syntax errors: `python -c "import data.updaters.fetcher_daily_price_tushare_v2"`

  **QA Scenarios**:

  ```
  Scenario: Datetime format is consistent
    Tool: Read
    Steps:
      1. Read line 185 of the file
      2. Verify it contains `.dt.strftime('%Y-%m-%d')`
    Expected Result: Line 185 converts to string format
    Evidence: .sisyphus/evidence/bug1-datetime-fix.md
  ```

  **Commit**: NO

---

- [ ] 2. Fix Bug 2: Add daily_basic stats tracking

  **What to do**:
  - Add `daily_basic_records = 0` after line 518 (`total_records = 0`)
  - After line 548 (`save_daily_basic(...)`), add `daily_basic_records += len(df_basic)`
  - Add `'total_daily_basic_records': daily_basic_records` to result dict (line 562-569)
  - Add log line after line 580: `logger.info(f"每日指标记录数: {result['total_daily_basic_records']}")`

  **Must NOT do**:
  - Do not change the logic flow, only add tracking

  **References**:
  - `data/updaters/fetcher_daily_price_tushare_v2.py:518` - Where to add counter
  - `data/updaters/fetcher_daily_price_tushare_v2.py:544-548` - daily_basic fetch/save block
  - `data/updaters/fetcher_daily_price_tushare_v2.py:562-569` - Result dict

  **Acceptance Criteria**:
  - [ ] `daily_basic_records` counter initialized
  - [ ] Counter incremented when daily_basic data saved
  - [ ] Counter added to result dict
  - [ ] Counter logged in final report

  **QA Scenarios**:

  ```
  Scenario: daily_basic stats tracked
    Tool: Read
    Steps:
      1. Read lines 518-570
      2. Verify daily_basic_records counter exists
      3. Verify counter is incremented after save_daily_basic
      4. Verify counter is in result dict
    Expected Result: All stats tracking elements present
    Evidence: .sisyphus/evidence/bug2-stats-fix.md
  ```

  **Commit**: NO

---

- [ ] 3. Fix Bug 3: Improve resume logic

  **What to do**:
  - Modify `get_latest_date_in_db` to check multiple tables
  - Or add a new function `get_earliest_latest_date` that:
    - Queries `adj_factor_tushare.MAX(trade_date)`
    - Queries `daily_price_raw.MAX(trade_date)`
    - Returns the MIN of both (earliest latest date to ensure no gaps)

  **Must NOT do**:
  - Do not change the function signature of `get_latest_date_in_db`

  **Alternative (simpler)**:
  - Just change line 489 to check `daily_price_raw` instead of `adj_factor_tushare`

  **References**:
  - `data/updaters/fetcher_daily_price_tushare_v2.py:430-451` - `get_latest_date_in_db` function
  - `data/updaters/fetcher_daily_price_tushare_v2.py:489` - Resume logic call site

  **Acceptance Criteria**:
  - [ ] Resume logic considers data availability across tables
  - [ ] No data gaps when resuming

  **QA Scenarios**:

  ```
  Scenario: Resume logic checks multiple tables
    Tool: Read
    Steps:
      1. Read lines 488-499
      2. Verify resume logic checks appropriate table(s)
    Expected Result: Resume logic robust
    Evidence: .sisyphus/evidence/bug3-resume-fix.md
  ```

  **Commit**: YES
  - Message: `fix(tushare): fix datetime, stats tracking, and resume bugs`
  - Files: `data/updaters/fetcher_daily_price_tushare_v2.py`

---

## Final Verification Wave

- [ ] F1. **Code Review** - `quick`
  Read the complete file. Verify all 3 fixes are present and correct. Check for syntax errors.
  Output: `Bug 1 [FIXED/MISSING] | Bug 2 [FIXED/MISSING] | Bug 3 [FIXED/MISSING] | VERDICT: APPROVE/REJECT`

---

## Success Criteria

### Verification Commands
```bash
python -c "import data.updaters.fetcher_daily_price_tushare_v2; print('Syntax OK')"
# Expected: Syntax OK (no errors)
```

### Final Checklist
- [ ] Bug 1: Datetime format consistent (string `%Y-%m-%d`)
- [ ] Bug 2: daily_basic stats tracked in counter, result dict, and log
- [ ] Bug 3: Resume logic checks appropriate tables
- [ ] No syntax errors
