"""Portable reports. External content is always escaped; no network dependencies."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .store import digest


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def table(values: dict) -> str:
    return "<table>" + "".join(
        f"<tr><th>{esc(k.replace('_', ' '))}</th><td>{esc('Unavailable' if v is None else str(v).replace('_', ' '))}</td></tr>"
        for k, v in values.items()
    ) + "</table>"


def chart(points: list[dict], key: str, label: str, color: str) -> str:
    if len(points) < 2:
        return "<p>Not enough data to draw this chart.</p>"
    values = [float(p[key]) for p in points]
    low, high = min(values), max(values)
    spread = high - low or 1
    coords = [(62 + i / (len(values) - 1) * 856, 205 - (v - low) / spread * 160)
              for i, v in enumerate(values)]
    line = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
    marks = "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{color}"><title>'
                    f'{esc(p["timestamp"][:10])}: {esc(p[key])}</title></circle>'
                    for (x, y), p in zip(coords, points))
    return (
        f'<svg viewBox="0 0 960 250" role="img" aria-label="{esc(label)}">'
        '<path d="M62 40V210H920" fill="none" stroke="#b1bdca"/>'
        f'<text x="8" y="50">{high:,.2f}</text><text x="8" y="205">{low:,.2f}</text>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.5"/>{marks}'
        f'<text x="62" y="237">{esc(points[0]["timestamp"][:10])}</text>'
        f'<text x="850" y="237">{esc(points[-1]["timestamp"][:10])}</text></svg>'
    )


def ai_section(report: dict) -> str:
    ai = report.get("ai_research")
    if not ai:
        return ""
    evidence = {e["id"]: e for e in ai["evidence"]}
    draft = ai["draft"]

    def claim_text(text):
        def replace(match):
            value = report
            for key in match[1].split("."):
                value = value[key]
            return str(value)
        return esc(re.sub(r"\{\{metric:([a-zA-Z0-9_.]+)\}\}", replace, text))

    sections = []
    for key, label in (("short_horizon", "2-12 weeks"), ("long_horizon", "6-24 months")):
        horizon = draft[key]
        body = f'<h3>{label}: {esc(horizon["stance"].replace("_", " "))}</h3>'
        for kind in ("thesis", "counterarguments", "catalysts"):
            claims = []
            for claim in horizon[kind]:
                citations = " ".join(
                    f'<a href="{esc(evidence[c["evidence_id"]]["source_url"])}">'
                    f'{esc(evidence[c["evidence_id"]]["title"])}</a> '
                    f'(available from {esc(evidence[c["evidence_id"]]["published_at"][:10])}): '
                    f'&ldquo;{esc(c["quote"])}&rdquo;' for c in claim["citations"])
                claims.append(f'<li><strong>{esc(claim["kind"])}</strong>: {claim_text(claim["text"])}'
                              f'<br><small>{citations}</small></li>')
            body += f'<h4>{kind.title()}</h4><ul>{"".join(claims) or "<li>No supported claim supplied.</li>"}</ul>'
        sections.append(body)
    gaps = "".join(f"<li>{claim_text(s)}</li>" for s in draft["missing_information"])
    return ('<section class="notice"><h2>AI research draft — human review pending</h2>'
            f'<p>{esc(draft["summary"])}</p><p>{esc(ai["validation"])}</p>'
            f'{"".join(sections)}<h3>Missing information</h3><ul>{gaps}</ul>'
            f'<details><summary>Generation and evidence coverage</summary>{table({k:ai[k] for k in ("generation_mode","model","model_identity_verified","prompt_version","usage","estimated_cost_usd","cost_status")})}'
            f'{table(ai["coverage"])}<p>Packet: {esc(ai["packet_hash"])}</p></details></section>')


def render(report: dict) -> str:
    instrument = report["instrument"]
    market = dict(report["market"])
    points = market.pop("chart", [])
    short = report["short_horizon"]
    long = report["long_horizon"]
    issues = sorted(set(sum(report["quality"].values(), [])))
    issue_html = "".join(f"<li>{esc(x)}</li>" for x in issues) or "<li>No configured data-quality checks failed.</li>"
    scenarios = "".join(
        f'<article class="scenario"><h3>{esc(name.title())}</h3>'
        f'<div class="value">{esc(s["present_value_proxy"])} <small>{esc(instrument["currency"])}</small></div>'
        f'<p>Gap to price: {esc(s["gap_to_price_pct"])}%</p>{table(s["assumptions"])}</article>'
        for name, s in long["scenarios"].items()
    ) or "<p>Valuation withheld. See data-quality findings.</p>"
    source_rows = "".join(
        f'<tr><td>{esc(s["metric"])}</td><td>{esc(s["value"])} {esc(s["unit"])}</td>'
        f'<td>{esc(s["period_end"])}</td><td>{esc(s["available_at"][:10])}</td>'
        f'<td>{esc(s["filing_id"])}</td></tr>' for s in report["sources"])
    source_links = sorted({s["source_url"] for s in report["sources"]} | set(report["market_sources"]))
    links = "".join(f'<li><a href="{esc(url)}">{esc(url)}</a></li>' if url.startswith("https://")
                    else f"<li>{esc(url)}</li>" for url in source_links)
    title = f'{instrument["name"]} | {instrument["id"]}'
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - Research report</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f7;color:#16283c;font:16px/1.55 system-ui,Arial}}
main{{max-width:1140px;margin:32px auto;padding:0 24px}}header{{background:#16324d;color:white;padding:32px;border-radius:16px}}
h1{{font-size:32px;line-height:1.2;margin:10px 0}}h2{{font-size:21px;margin:0 0 16px}}h3{{margin:0 0 12px}}
.label{{font-size:13px;letter-spacing:1px;color:#ffdb80}}.muted{{color:#62738a}}header .muted{{color:#d1deeb}}
section,.scenario{{background:white;padding:24px;border:1px solid #d9e1eb;border-radius:12px;margin-top:20px;overflow-wrap:anywhere}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.scenarios{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.scenario{{margin:0;background:#f7fafc;padding:18px}}.value{{font-size:26px;font-weight:700}}small{{font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px 8px;text-align:left;vertical-align:top;border-bottom:1px solid #e4eaf1}}
th{{font-weight:600;width:44%}}.source th{{width:auto}}.scroll{{overflow-x:auto}}svg{{width:100%;display:block}}svg text{{font:12px system-ui;fill:#52677c}}
a{{color:#1c5e94}}li{{margin:6px 0}}.notice{{border-left:5px solid #d49624}}pre{{white-space:pre-wrap;font-size:12px}}
@media(max-width:780px){{.grid,.scenarios{{grid-template-columns:1fr}}main{{padding:0 12px}}header{{padding:22px}}}}
</style><main>
<header><div class="label">{esc(report["data_label"])}</div><h1>{esc(title)}</h1>
<p>Numerical stock research | {esc(instrument["currency"])} | {esc(instrument.get("sector", "unknown"))}</p>
<p class="muted">Information cutoff: {esc(report["as_of"])}<br>Separate views for 2-12 weeks and 6-24 months.</p></header>
<section class="notice"><h2>How to read this report</h2>
<p>Reference levels and valuation ranges are hypotheses for review. They are not validated buy/sell signals.
Historical drawdown does not cap future losses. This report does not place orders.</p></section>
<div class="grid"><section><h2>2-12 weeks: price setup</h2>{table(short)}</section>
<section><h2>6-24 months: valuation screen</h2>{table({k:v for k,v in long.items() if k!="scenarios"})}</section></div>
<section><h2>Price history ({esc(instrument["currency"])}), adjusted</h2>{chart(points,"close","Adjusted close history","#246c9a")}</section>
<section><h2>Decline from historical price peak (%)</h2>{chart(points,"drawdown_pct","Historical price drawdown","#b5613b")}</section>
<section><h2>Earnings valuation scenarios</h2><p class="muted">Discounted terminal P/E proxies; assumptions below are configurable and do not come from analyst consensus.</p>
<div class="scenarios">{scenarios}</div></section>
<div class="grid"><section><h2>Price and downside measurements</h2>{table(market)}</section>
<section><h2>Annual financial measurements</h2>{table({k:v for k,v in report["financials"].items() if k!="values"})}</section></div>
<section class="notice"><h2>Data-quality findings</h2><ul>{issue_html}</ul></section>
{ai_section(report)}
<section><h2>Financial evidence</h2><div class="scroll"><table class="source"><tr><th>Metric</th><th>Value</th><th>Period end</th><th>Available</th><th>Filing</th></tr>{source_rows}</table></div><ul>{links}</ul></section>
<section><h2>Limits and assumptions</h2><ul>{"".join("<li>"+esc(x)+"</li>" for x in report["limitations"])}</ul>
<details><summary>Reproduction identifiers and assumptions</summary><pre>{esc(json.dumps({k:report[k] for k in ("engine_version","input_hash","assumptions_hash","snapshot_ids","assumptions")}, indent=2))}</pre></details></section>
<p class="muted">Report content ID: {digest(report)}. Sources and raw snapshots are retained in the local research database.</p>
</main></html>"""


def write_report(report: dict, directory: str | Path) -> dict:
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    basename = report["instrument"]["id"].replace(":", "-") + "-" + digest(report)[:12]
    paths = {extension: folder / f"{basename}.{extension}" for extension in ("json", "html")}
    paths["json"].write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    paths["html"].write_text(render(report), encoding="utf-8")
    return {kind: str(path.resolve()) for kind, path in paths.items()}
