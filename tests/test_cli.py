from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_diagnostics_cli_handles_missing_chroma(tmp_path: Path) -> None:
    script = Path("scripts/hydra_diag.py").resolve()
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root / 'src'}" + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.run(
        [sys.executable, str(script), "tasks"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert process.returncode != 0
    assert "Chroma unavailable" in process.stdout
