"""Real issuer disclosures for the M4 examples; no broker or model credentials."""
import json
from pathlib import Path

from toss_pilot.config import REPO_ROOT
from toss_pilot.research.ai import build_packet
from toss_pilot.research.evidence import collect_document
from toss_pilot.research.store import Store, now

SOURCES = [
    dict(identity="US:AAPL", url="https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/",
         title="Apple fiscal third-quarter results, July 2026", published_at="2026-07-31T00:00:00+00:00",
         start_text="CUPERTINO, CALIFORNIA", end_text="The Company assumes no obligation"),
    dict(identity="KR:005930", url="https://news.samsung.com/global/samsung-electronics-announces-second-quarter-2026-results",
         title="Samsung second-quarter results, July 2026", published_at="2026-07-31T00:00:00+00:00",
         start_text="Quarterly revenue of KRW", end_text="For any issues related to customer service"),
    dict(identity="KR:005930", url="https://news.samsung.com/global/samsung-electronics-announces-earnings-guidance-for-third-quarter-2026",
         title="Samsung preliminary third-quarter guidance, October 2026", published_at="2026-10-09T00:00:00+00:00",
         start_text="Samsung Electronics today announced its earnings guidance", end_text="For any issues related to customer service"),
]


def main():
    folder = REPO_ROOT / "data" / "research-packets"
    folder.mkdir(parents=True, exist_ok=True)
    result = {"started_at": now(), "sources": []}
    with Store(REPO_ROOT / "data" / "live.sqlite3") as store:
        for source in SOURCES:
            item = {"instrument_id": source["identity"], "url": source["url"]}
            try:
                identifier = collect_document(store, **source)
                item.update(status="succeeded", document_id=identifier)
            except Exception as exc:
                item.update(status="failed", error_type=type(exc).__name__)
            result["sources"].append(item)
            print(json.dumps(item), flush=True)
        result["packets"] = []
        for identity in ("US:AAPL", "KR:005930"):
            packet = build_packet(store, identity, now())
            path = folder / (identity.replace(":", "-") + ".json")
            path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
            result["packets"].append({"instrument_id": identity, "packet_hash": packet["packet_hash"],
                                      "file": str(path), "coverage": packet["coverage"], "required_stances": packet["required_stances"]})
        result["finished_at"] = now()
        (REPO_ROOT / "docs" / "evidence" / "live" / "disclosures.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
