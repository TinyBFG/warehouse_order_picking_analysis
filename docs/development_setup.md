# Python development setup

Run these commands in PowerShell from the project root (the directory containing `requirements-dev.txt`). Python 3.14.5, 64-bit Windows, and pytest 9.1.1 are the validation baseline for this task. Other Python versions have not been verified for this project.

## Dependencies

The existing inventory script uses only Python's standard library. There is no production dependency file because no third-party runtime package is currently needed. `requirements-dev.txt` pins pytest, the test runner. pip will also install pytest's dependencies; those transitive packages are not locked by this file. This is a minimal setup, not a complete cross-platform environment lock.

## 1. Confirm the base interpreter

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

Confirm that these commands select an installed Python interpreter. On this computer, the WindowsApps `python` alias previously failed to launch. If it fails or selects the wrong version, use the full path to the desired installed `python.exe`, prefixed with PowerShell's `&` operator, in place of `python` for the environment-creation command below. Do not assume the command name selects the right interpreter.

## 2. Create an isolated environment

Create it only if `.venv` does not already exist:

```powershell
python -m venv .venv
```

A virtual environment gives this project its own Python entry point and installed packages. It does not copy the source dataset. `.venv/` is already excluded by `.gitignore`; it should not be committed. If an environment already exists, inspect its Python version rather than overwriting it.

The remaining commands call its executable directly. PowerShell activation and execution-policy changes are unnecessary.

## 3. Install test dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import sys, pytest; print(sys.version); print('pytest', pytest.__version__)"
```

Installation needs access to the package index unless the packages are already cached. `python.exe -m pip` ties pip to this environment, preventing accidental installation into a different interpreter. `pip check` reports incompatible or missing installed dependencies; it does not run project tests.

## 4. Run the focused tests

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --tb=short tests/test_inspect_sources.py
```

Expected result for the current suite: 10 passing tests. `-B` suppresses Python bytecode-cache writes; `-p no:cacheprovider` disables pytest's project cache. Test fixtures still require writable temporary storage. The tests create their own small CSV fixtures and do not depend on the raw download.

If temporary-directory creation fails in a restricted execution environment, treat it as an environment/setup failure, not evidence that the assertions passed or failed. Resolve the permission issue and rerun the same tests. Do not change source data to make a test pass.

## 5. Inspect the local source CSVs

With the original downloaded files available in `data/raw/`:

```powershell
.\.venv\Scripts\python.exe -B scripts/inspect_sources.py
```

The script prints one JSON summary per top-level CSV to the terminal. It writes no report file and changes no source files. For the current download, expect nine summaries, zero malformed-width records, and 16 blank `Size (US)` fields in `Customer_Order.csv`.

Without an explicit directory, the script finds `data/raw/` relative to its own project location rather than the terminal's working directory. A different source directory can be supplied as its positional argument. The supported parsing assumptions are documented in the script.

Exit status meanings:

- `0`: files were inspected without read/parse errors or malformed row widths. Blank fields alone do not cause failure.
- `1`: at least one file had a read/parse error or malformed row width.
- `2`: invalid usage, a missing source directory, or no top-level CSVs.

Successful structural inspection does not validate quantities, duplicate meaning, keys, relationships, or operational conclusions. See [source dictionary](source_data_dictionary.md) and [size investigation](size_normalization.md).

## Git and generated files

Commit `requirements-dev.txt` and this document after reviewing the working tree. Do not commit `.venv/`, Python caches, test temporary files, or raw data. No Git staging, commit, or push is part of these setup commands.

There is no database build or analytical pipeline command yet. This document covers only the implemented inventory script and tests. Dependency installation does not establish source acquisition rights or provide the raw download; see [source provenance](source_provenance.md).
