"""Install the built wheel in a fresh environment; run from outside the checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
wheel = next((root / "dist").glob(f"toss_pilot-{version}-*.whl"))
cache = root / ".pytest_cache" / "wheel"
cache.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=cache) as directory:
    work = Path(directory)
    env = work / "env"
    subprocess.run(["uv", "venv", "--python", sys.executable, str(env)], check=True)
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirements = work / "requirements.txt"
    subprocess.run(["uv", "export", "--locked", "--no-dev", "--no-emit-project",
                    "--output-file", str(requirements)], cwd=root, check=True, capture_output=True)
    subprocess.run(["uv", "pip", "install", "--python", str(python),
                    "-r", str(requirements), str(wheel)], check=True)
    code = """
import json
from pathlib import Path
import toss_pilot
from toss_pilot.config import load_config, DEFAULT_CONFIG_PATH
assert 'site-packages' in str(Path(toss_pilot.__file__).resolve())
assert load_config()['base_url'] == 'https://openapi.tossinvest.com'
assert DEFAULT_CONFIG_PATH.is_file()
from toss_pilot.research.ai import build_packet, import_draft
from toss_pilot.research.store import Store, now
with Store('m4.sqlite3') as store:
    identity = store.register({'market':'US','symbol':'EMPTY','currency':'USD'})
    packet = build_packet(store, identity, now())
    horizon = {'stance':'insufficient_data','thesis':[], 'counterarguments':[], 'catalysts':[]}
    draft = {'schema_version':1,'packet_hash':packet['packet_hash'], 'status':'abstain',
             'summary':'Research draft for human review; consult the cited evidence and data gaps.',
             'short_horizon':horizon,'long_horizon':horizon,'missing_information':['No evidence available.']}
    result = import_draft(store, draft, model='wheel smoke test', output='m4-reports')
    assert result['draft_status'] == 'abstain'
print(json.dumps({'version': toss_pilot.__version__, 'installed_config': True}))
"""
    completed = subprocess.run([str(python), "-c", code], cwd=work, check=True, capture_output=True, text=True)
    subprocess.run([str(python), "-m", "toss_pilot.cli", "--help"], cwd=work, check=True, capture_output=True)
    subprocess.run([str(python), "-m", "toss_pilot.research.cli", "demo", "--output", str(work / "demo")],
                   cwd=work, check=True, capture_output=True)
    print(completed.stdout.strip())
    print("Wheel CLI and offline demo passed outside the repository")
