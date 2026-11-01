"""Exercise complete builds with tiny source files, including safe rebuilding."""

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from scripts.build_database import build_database, main


@pytest.fixture
def sources(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "Product.csv").write_text("Reference;ABCCOD;Sector\nP1;A;PF\n", encoding="utf-8")
    (raw / "Storage_Location.csv").write_text(
        'originalLocation,position,x,y,z\nL1,"1,2,3",1,2,3\n', encoding="utf-8"
    )
    (raw / "Customer_Order.csv").write_text(
        "codCustomer;orderNumber;orderToCollect;Reference;Size (US);quantity (units);"
        "creationDate;waveNumber;operator\n"
        "C1;O1;1;P1;95;1;05/01/2023 07:42;W1;OP1\n", encoding="utf-8"
    )
    (raw / "Picking_Wave.csv").write_text(
        "waveNumber;reference;Size (US);quantityToPick (units);locations;operator\n"
        "W1;P1;9.5;1;L1;OP1\n", encoding="utf-8"
    )
    return raw


def database_dump(path):
    db = sqlite3.connect(path)
    try:
        return '\n'.join(db.iterdump())
    finally:
        db.close()


def test_build_loads_all_files_and_keeps_sources_unchanged(sources, tmp_path):
    output = tmp_path / "generated" / "warehouse.sqlite"
    before = {p.name: p.read_bytes() for p in sources.iterdir()}
    report = build_database(sources, output)
    assert report["database_path"] == str(output.resolve())
    assert report["loaded_records"] == {name: 1 for name in before}
    assert report["relationship_checks"]["status"] == "ok"
    assert report["integrity_check"] == "ok"
    assert {p.name: p.read_bytes() for p in sources.iterdir()} == before
    for item in report["source_files"]:
        raw = before[item["file_name"]]
        assert item["sha256"] == hashlib.sha256(raw).hexdigest()
        assert item["size_bytes"] == len(raw)
        assert item["record_count"] == 1
    assert output.is_file()
    assert list(output.parent.glob("warehouse-build-*")) == []


def test_repeat_without_replace_preserves_database(sources, tmp_path):
    output = tmp_path / "warehouse.sqlite"
    build_database(sources, output)
    original = output.read_bytes()
    with pytest.raises(FileExistsError, match="--replace"):
        build_database(sources, output)
    assert output.read_bytes() == original


def test_replace_rebuilds_identical_contents_without_appending(sources, tmp_path):
    output = tmp_path / "warehouse.sqlite"
    first_report = build_database(sources, output)
    original = database_dump(output)
    second_report = build_database(sources, output, replace=True)
    assert database_dump(output) == original
    assert second_report == first_report


def test_same_sources_build_same_contents_at_another_path(sources, tmp_path):
    first, second = tmp_path / "first.sqlite", tmp_path / "second.sqlite"
    build_database(sources, first)
    build_database(sources, second)
    assert database_dump(first) == database_dump(second)


@pytest.mark.parametrize("replace", [False, True])
def test_late_load_failure_keeps_existing_database_or_leaves_no_output(sources, tmp_path, replace):
    output = tmp_path / "warehouse.sqlite"
    if replace:
        build_database(sources, output)
        original = output.read_bytes()
    path = sources / "Picking_Wave.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("W1;P1;", "W1;UNKNOWN;"), encoding="utf-8")
    with pytest.raises(sqlite3.IntegrityError):
        build_database(sources, output, replace=replace)
    if replace:
        assert output.read_bytes() == original
    else:
        assert not output.exists()
    assert list(tmp_path.glob("warehouse-build-*")) == []


def test_known_coverage_warnings_allow_build(sources, tmp_path):
    path = sources / "Picking_Wave.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(";L1;", ";UNKNOWN;"), encoding="utf-8")
    report = build_database(sources, tmp_path / "warehouse.sqlite")
    assert report["relationship_checks"]["status"] == "warning"
    assert report["relationship_checks"]["errors"] == []
    assert report["relationship_checks"]["location_coverage"]["unmatched_records"] == 1


def test_relationship_error_stops_publication(sources, tmp_path, monkeypatch):
    from scripts import build_database as module
    monkeypatch.setattr(module, "check_relationships", lambda db: {
        "status": "error", "errors": ["required_tables_empty"],
    })
    output = tmp_path / "warehouse.sqlite"
    with pytest.raises(ValueError, match="Relationship checks failed"):
        build_database(sources, output)
    assert not output.exists()
    assert list(tmp_path.glob("warehouse-build-*")) == []


def test_missing_source_is_reported_before_creating_output(sources, tmp_path):
    (sources / "Product.csv").unlink()
    output = tmp_path / "generated" / "warehouse.sqlite"
    with pytest.raises(FileNotFoundError, match="Product.csv"):
        build_database(sources, output)
    assert not output.parent.exists()


def test_database_cannot_be_written_inside_raw_directory(sources):
    with pytest.raises(ValueError, match="outside raw"):
        build_database(sources, sources / "warehouse.sqlite", replace=True)


def test_output_must_have_database_extension(sources, tmp_path):
    with pytest.raises(ValueError, match="must end"):
        build_database(sources, tmp_path / "README.md", replace=True)


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_sqlite_companion_files_prevent_replacement(sources, tmp_path, suffix):
    output = tmp_path / "warehouse.sqlite"
    build_database(sources, output)
    original = output.read_bytes()
    companion = output.with_name(output.name + suffix)
    companion.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="companion"):
        build_database(sources, output, replace=True)
    assert output.read_bytes() == original
    assert companion.read_bytes() == b"fixture"


def test_cli_prints_json_on_success(sources, tmp_path, capsys):
    output = tmp_path / "warehouse.sqlite"
    assert main(["--source-dir", str(sources), "--database", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["relationship_checks"]["status"] == "ok"


def test_cli_failure_is_nonzero_and_does_not_create_database(tmp_path, capsys):
    output = tmp_path / "warehouse.sqlite"
    with pytest.raises(SystemExit) as error:
        main(["--source-dir", str(tmp_path / "missing"), "--database", str(output)])
    assert error.value.code == 1
    assert "Build failed:" in capsys.readouterr().err
    assert not output.exists()
