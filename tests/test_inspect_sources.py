"""Small fixtures verify CSV parsing and error reporting without using raw data."""

import json

import pytest

from scripts.inspect_sources import inspect_csv, main


def test_comma_csv_preserves_quoted_semicolons_and_source_bytes(tmp_path):
    path = tmp_path / "storage.csv"
    original = b'location,slot\r\nA-01,"PRODUCT;9.5"\r\n'
    path.write_bytes(original)
    report = inspect_csv(path)
    assert report["delimiter"] == ","
    assert report["headers"] == ["location", "slot"]
    assert report["record_count"] == 1
    assert report["malformed_width_record_count"] == 0
    assert path.read_bytes() == original


def test_semicolon_csv_handles_bom_quotes_multiline_and_blanks(tmp_path):
    path = tmp_path / "orders.csv"
    path.write_text('name;note;size\n"a;b";"first\nsecond"; \nx;ok;9\n',
                    encoding="utf-8-sig")
    report = inspect_csv(path)
    assert report["delimiter"] == ";"
    assert report["headers"] == ["name", "note", "size"]
    assert report["record_count"] == 2
    assert report["blank_fields_in_valid_width_records"] == {
        "name": 0, "note": 0, "size": 1,
    }


def test_wrong_width_and_empty_rows_are_counted_separately(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("a,b\n1,\n2\n3,4,5\n\n", encoding="utf-8")
    report = inspect_csv(path)
    assert report["record_count"] == 4
    assert report["valid_width_record_count"] == 1
    assert report["malformed_width_record_count"] == 3
    assert report["blank_fields_in_valid_width_records"] == {"a": 0, "b": 1}


@pytest.mark.parametrize("content", ["", "a,a\n1,2\n", "a,\n1,2\n"])
def test_invalid_headers_are_rejected(tmp_path, content):
    path = tmp_path / "bad.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        inspect_csv(path)


def test_cli_reports_parse_failure_and_continues(tmp_path, capsys):
    (tmp_path / "a.csv").write_text('a,b\n"unterminated,2\n', encoding="utf-8")
    (tmp_path / "b.CSV").write_text("a;b\n1;2\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert reports[0]["file"] == "a.csv"
    assert "error" in reports[0]
    assert reports[1]["record_count"] == 1


def test_cli_returns_failure_for_malformed_width(tmp_path, capsys):
    (tmp_path / "bad.csv").write_text("a,b\n1\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["malformed_width_record_count"] == 1


def test_cli_success_ignores_non_csv_files(tmp_path, capsys):
    (tmp_path / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a CSV", encoding="utf-8")
    assert main([str(tmp_path)]) == 0
    reports = capsys.readouterr().out.splitlines()
    assert len(reports) == 1
    assert json.loads(reports[0])["file"] == "data.csv"


def test_cli_rejects_empty_source_directory(tmp_path):
    with pytest.raises(SystemExit) as error:
        main([str(tmp_path)])
    assert error.value.code == 2
