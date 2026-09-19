import pathlib
from datetime import datetime, timedelta

today = datetime.now().date()
rows = []
for base in ("src", "tests", "docs", "website", "extensions"):
    root = pathlib.Path(base)
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if ".git" in p.parts or "node_modules" in p.parts:
            continue
        m = datetime.fromtimestamp(p.stat().st_mtime)
        if m.date() == today:
            rows.append((m.strftime("%H:%M"), str(p)))
rows.sort()
print(f"files touched today: {len(rows)}")
for t, p in rows:
    print(t, p)