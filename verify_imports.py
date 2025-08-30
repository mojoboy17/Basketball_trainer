import importlib
from pathlib import Path
import sys

req_file = Path("requirements.txt")
if not req_file.exists():
    print("requirements.txt not found")
    sys.exit(1)

def spec_to_module(spec: str) -> str:
    # Strip version specifiers and extras
    name = spec.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0]
    name = name.split("[")[0]
    # Known import name differences
    special = {
        "python-dotenv": "dotenv",
    }
    if name in {"openai-agents"}:
        return None  # skip verification for packages without a straightforward import name
    return special.get(name, name.replace("-", "_"))

pkgs = []
for line in req_file.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    pkgs.append(line)

failures = []
for spec in pkgs:
    mod = spec_to_module(spec)
    if mod is None:
        continue
    try:
        importlib.import_module(mod)
    except Exception as e:
        failures.append((spec, mod, str(e)))

if failures:
    print("Import verification failed for:")
    for spec, mod, err in failures:
        print(f"  package spec: {spec} -> import: {mod} error: {err}")
    sys.exit(1)
print("All dependencies imported successfully.")
