"""Unit test: check_layers.sh rejects framework imports in app/domain/."""

import subprocess
from pathlib import Path


def test_layer_check_rejects_fastapi_import_in_domain() -> None:
    """check_layers.sh exits non-zero when a file in app/domain imports fastapi."""
    leak_path = Path("app/domain/products/leak.py")
    leak_path.write_text("import fastapi\n")
    try:
        result = subprocess.run(
            ["bash", "scripts/check_layers.sh"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, "check_layers.sh should fail with a domain layer violation"
        assert "leak.py" in result.stderr or "fastapi" in result.stderr
    finally:
        leak_path.unlink(missing_ok=True)


def test_layer_check_passes_for_clean_domain() -> None:
    """check_layers.sh exits zero when domain layer has no framework imports."""
    result = subprocess.run(
        ["bash", "scripts/check_layers.sh"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"check_layers.sh failed unexpectedly: {result.stderr}"
