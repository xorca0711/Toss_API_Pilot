"""Retrieve public contracts, retain immutable copies, and record drift/failures."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="docs/evidence/contracts")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
baseline = json.loads((root / "spec/openapi-1.2.14.json").read_text(encoding="utf-8"))
result = {"checked_at": datetime.now(timezone.utc).isoformat(), "sources": []}
for kind, url in (
    ("rest", "https://openapi.tossinvest.com/openapi-docs/latest/openapi.json"),
    ("streaming", "https://openapi.tossinvest.com/openapi-docs/latest/asyncapi.json"),
):
    entry = {"kind": kind, "url": url}
    try:
        response = httpx.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
        required = "paths" if kind == "rest" else "channels"
        if required not in data:
            raise ValueError("Response is not the expected contract")
        sha = hashlib.sha256(response.content).hexdigest()
        filename = f"{kind}-{sha[:12]}.json"
        (out / filename).write_bytes(response.content)
        entry.update(status="retrieved", sha256=sha, file=filename,
                     version=data.get("info", {}).get("version"), entries=len(data[required]))
        if kind == "rest":
            entry["added_paths"] = sorted(set(data["paths"]) - set(baseline["paths"]))
            entry["removed_paths"] = sorted(set(baseline["paths"]) - set(data["paths"]))
            entry["changed_paths"] = sorted(p for p in set(data["paths"]) & set(baseline["paths"])
                                            if data["paths"][p] != baseline["paths"][p])
    except Exception as exc:
        entry.update(status="unavailable", error_type=type(exc).__name__)
    result["sources"].append(entry)
(out / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
