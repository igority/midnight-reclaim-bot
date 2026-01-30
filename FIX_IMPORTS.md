# FIX_IMPORTS.md - Manual Steps to Fix Import Issues

## Issue: `logging` folder conflicts with Python's built-in logging module

---

## Step 1: Rename the Folder

### Windows (PowerShell):
```powershell
cd "C:\Projects\Trading\Midnight reclaim bot\midnight_reclaim_bot"
Rename-Item -Path "logging" -NewName "strategy_logging"
```

### Windows (Command Prompt):
```cmd
cd "C:\Projects\Trading\Midnight reclaim bot\midnight_reclaim_bot"
rename logging strategy_logging
```

---

## Step 2: Install Missing Package

```bash
pip install pyyaml
```

---

## Step 3: Replace Test Files

1. Delete old test files:
   - `test_sprint1.py`
   - `test_sprint2.py`

2. Rename fixed files:
   - `test_sprint1_FIXED.py` → `test_sprint1.py`
   - `test_sprint2_FIXED.py` → `test_sprint2.py`

---

## Step 4: Update Imports in Other Files

Find and replace in these files:

### Files to update:
- `core/shadow_trades.py`
- `core/indicators.py` (if it imports logging)
- Any other files that import from `logging`

### Find:
```python
from logging.
```

### Replace with:
```python
from strategy_logging.
```

---

## Step 5: Verify Structure

Your project should now look like:

```
midnight_reclaim_bot/
├── config/
├── core/
├── data/
├── strategy_logging/     ← RENAMED (was "logging")
│   ├── __init__.py
│   ├── schemas.py
│   └── logger.py
├── utils/
├── test_sprint1.py       ← FIXED
├── test_sprint2.py       ← FIXED
└── ...
```

---

## Step 6: Test

```bash
# Test Sprint 1
python test_sprint1.py

# Test Sprint 2
python test_sprint2.py
```

---

## Quick Reference: Files That Import Logging

These files may need updating (if they exist and import logging):

1. `core/shadow_trades.py`
2. `test_sprint1.py` (already fixed in _FIXED version)
3. `test_sprint2.py` (already fixed in _FIXED version)

Search pattern: `from logging.` or `import logging.`
Replace with: `from strategy_logging.` or `import strategy_logging.`

---

## Alternative: Use Search & Replace in VS Code

1. Open VS Code
2. Press `Ctrl+Shift+H` (Find & Replace in Files)
3. Find: `from logging\.`
4. Replace: `from strategy_logging.`
5. Files to include: `*.py`
6. Click "Replace All"

---

## After Fixes Complete

Run both tests:

```bash
python test_sprint1.py
python test_sprint2.py
```

Both should now pass! ✅
