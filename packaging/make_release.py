"""Create separate Windows application and source archives without personal state."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ", "000001.SS")


def add_file(archive, path, name):
    archive.write(path, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    runtime = ROOT / "dist/QuantDesk"
    if not (runtime / "QuantDesk.exe").is_file() or not (runtime / "_internal").is_dir():
        raise SystemExit("Run build.ps1 first: EXE and _internal are required.")
    sample = ROOT / "data/aapl.csv"
    if not sample.is_file():
        raise SystemExit("Missing data/aapl.csv: run download_data.py first.")
    commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = ROOT / "releases" / f"{stamp}-{commit}"
    destination.mkdir(parents=True, exist_ok=False)
    samples = [path for symbol in SYMBOLS for suffix in (".csv", ".source.json")
               if (path := ROOT / "data/demo" / f"{symbol}{suffix}").is_file()]
    docs = [(ROOT / "docs/quickstart.md", "README.md"),
            (ROOT / "docs/market-data.md", "docs/market-data.md")]
    app_zip = destination / "QuantDesk-Windows-x64.zip"
    with zipfile.ZipFile(app_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(runtime.rglob("*")):
            if path.is_file():
                if path.suffix.lower() in {".db", ".sqlite3", ".log"} or path.name.startswith(".env"):
                    raise SystemExit(f"Unexpected personal state in runtime: {path.name}")
                add_file(archive, path, "QuantDesk/" + path.relative_to(runtime).as_posix())
        for path, name in docs:
            add_file(archive, path, "QuantDesk/" + name)
        for path in samples:
            add_file(archive, path, "QuantDesk/samples/" + path.name)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    allowed_roots = {"quantdesk", "tests", "docs", "packaging", "web"}
    allowed_files = {"README.md", "start.ps1", "build.ps1", "desktop.py",
                     "download_data.py", "engine.py", "server.py", "requirements.txt", "requirements-dev.txt", ".gitignore"}
    source_zip = destination / "QuantDesk-Source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(filter(None, tracked)):
            relative = Path(name)
            path = ROOT / relative
            if (name in allowed_files or relative.parts[0] in allowed_roots) and path.is_file():
                if path.suffix.lower() in {".db", ".sqlite3", ".log", ".exe", ".dll", ".pyc"} or path.name.startswith(".env"):
                    raise SystemExit(f"Unexpected sensitive/generated source file: {name}")
                add_file(archive, path, "QuantDesk-Source/" + relative.as_posix())
        add_file(archive, sample, "QuantDesk-Source/data/aapl.csv")
        for path in samples:
            add_file(archive, path, "QuantDesk-Source/data/demo/" + path.name)
    records = []
    for path in (app_zip, source_zip):
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        records.append({"file": path.name, "bytes": path.stat().st_size, "sha256": digest})
    (destination / "manifest.json").write_text(json.dumps({"commit": commit, "packages": records}, indent=2), encoding="utf-8")
    (destination / "SHA256SUMS.txt").write_text("".join(f"{r['sha256']}  {r['file']}\n" for r in records), encoding="utf-8")
    print(json.dumps({"directory": str(destination), "packages": records}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
