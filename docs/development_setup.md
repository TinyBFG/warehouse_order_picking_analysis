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

## 4. Run the test suite

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --tb=short tests
```

Expected result: all tests pass. The suite covers CSV inspection, schema constraints, all four loaders, relationship checks, and database builds. `-B` suppresses Python bytecode-cache writes; `-p no:cacheprovider` disables pytest's project cache. Test fixtures still require writable temporary storage. The tests create their own small CSV fixtures and do not depend on the raw download.

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

Commit useful source code, SQL, tests, documentation, and dependency files after reviewing the working tree. Do not commit `.venv/`, generated databases, Python caches, test temporary files, or raw data. No Git staging, commit, or push is part of these setup commands.

## 6. Build the SQLite database

From the project root:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.build_database
```

This creates `data/warehouse.sqlite` from four required files: `Product.csv`, `Storage_Location.csv`, `Customer_Order.csv`, and `Picking_Wave.csv`. The storage-scenario and navigation CSVs are not loaded by this command.

The build initializes `sql/schema.sql`, runs the existing loaders, checks relationships and SQLite integrity, and prints a JSON report. Source metadata includes each loaded file's SHA-256, byte count, and record count. Identifiers are normalized as documented by each loader; raw size values, repeated records, blank order sizes, and zero quantities are retained. No size mapping is applied.

The supplied snapshot should load 208 products, 2,292 locations, 122,370 order records, and 215,192 picking records. Known relationship warnings remain: 22 unmatched picking location codes affecting 23,609 records, and 77 order waves without picking records. These warnings permit a build; errors prevent it. Successful loading is not proof of completed picking, order fulfillment, or analytical correctness.

An existing output is refused. To explicitly rebuild from the current sources:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.build_database --replace
```

Each rebuild starts from an empty staged database; it never appends to the old one. Loading and validation finish before replacement, and connections are closed before moving the staged file. The old database remains intact if building fails. Temporary staging files are removed on normal completion or failure. The staging folder is beside the destination to avoid an extra database copy.

Close other database connections/viewers before replacement. The builder refuses replacement when SQLite companion files (`-wal`, `-shm`, or `-journal`) are present. It does not delete those files or resolve another program's locks. File operations are verified on the Windows setup described above.

Optional arguments:

- `--source-dir` selects the directory containing the four required filenames. Defaults are resolved relative to the project, not the working directory.
- `--database` selects an output ending in `.sqlite`, `.sqlite3`, or `.db`. Relative overrides are resolved from the working directory. Output inside the selected source directory or the project's default raw directory is rejected.
- `--replace` permits replacing the existing destination after a successful fresh build.

Run from the project root so Python can import the `scripts` module. Use `-m scripts.build_database`, not `python scripts/build_database.py`.

Exit codes: `0` means the database was saved successfully, possibly with reported warnings; `1` means a source, loading, validation, or file-operation failure; `2` means invalid command-line usage. A failure is printed to stderr. The JSON report goes to stdout on success and is not saved as a separate artifact.

Reproducibility means identical source bytes and schema produce the same stored records, source links, and check results; byte-for-byte SQLite file identity is not a cross-version promise. Dependencies and SQLite versions can affect file representation.

There is no analytical query pipeline yet. Dependency installation and database building do not establish source acquisition rights or provide the raw download; see [source provenance](source_provenance.md).
