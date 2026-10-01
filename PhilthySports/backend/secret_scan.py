from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    "openai_style_secret": re.compile(r"sk-[A-Za-z0-9]{24,}"),
}

SKIP_NAMES = {".git", "build", ".dart_tool", "__pycache__"}

findings: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in SKIP_NAMES for part in path.parts):
        continue
    if path.suffix.lower() not in {".py", ".dart", ".md", ".yaml", ".yml", ".txt", ".example"}:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            findings.append(f"{path.relative_to(ROOT)}: {name}")

if findings:
    raise SystemExit("Potential committed secrets found:\n" + "\n".join(findings))

print("PhilthySports source secret scan: PASS (zero findings)")
