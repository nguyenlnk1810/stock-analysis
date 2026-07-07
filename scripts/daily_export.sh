#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
LOG="$HOME/Library/Logs/stock-export.log"

echo "=== $(date) ===" >> "$LOG"
"$PWD/venv/bin/python3" "$PWD/export_data.py" >> "$LOG" 2>&1
EXIT=$?
echo "Export exit code: $EXIT" >> "$LOG"

if [ $EXIT -eq 0 ]; then
    git add -A >> "$LOG" 2>&1
    TODAY=$(date '+%Y-%m-%d')
    git commit -m "daily update $TODAY" >> "$LOG" 2>&1 || echo "Nothing to commit" >> "$LOG"
    git push >> "$LOG" 2>&1
    echo "Push done" >> "$LOG"
fi
echo "=== End ===" >> "$LOG"
