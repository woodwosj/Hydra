from pathlib import Path
import textwrap

import pytest

from hydra_mcp.profiles import ProfileLoadError, ProfileLoader


def write_profile(path: Path, *, title: str) -> None:
    path.write_text(
        textwrap.dedent(
            """
            id: sample
            title: {title}
            persona: Persona
            system_prompt: Prompt
            goalset:
              - goal
            constraints:
              - constraint
            checklist_template:
              - id: step
                description: do something
            """
        ).strip().format(title=title),
        encoding="utf-8",
    )


def test_loader_merges_paths(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    override = tmp_path / "override"
    override.mkdir()

    write_profile(base / "sample.yaml", title="Base Title")
    write_profile(override / "sample.yaml", title="Override Title")

    loader = ProfileLoader([base, override])
    profiles = loader.load_all()

    assert profiles["sample"].title == "Override Title"


def test_loader_handles_missing_profiles(tmp_path: Path) -> None:
    loader = ProfileLoader([tmp_path])
    assert loader.load_all() == {}


def test_loader_reports_validation_error(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "broken.yaml").write_text("id: \npersona: test", encoding="utf-8")

    loader = ProfileLoader([invalid])

    with pytest.raises(ProfileLoadError):
        loader.load_all()
