"""Create an allowlisted source archive, excluding secrets and local artifacts."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md", ".env.example", ".gitignore", ".vercelignore", ".python-version", "app.py",
    "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts", "vercel.json", "playwright.config.ts",
    "requirements.txt", "requirements-web.txt", "requirements-streamlit.txt", "pyproject.toml", "index.html",
    "data/sample_feedback.csv", "docs/web_demo.md", "docs/streamlit_legacy.md",
    "scripts/export_web_demo.py", "scripts/evaluate_web.py", "scripts/smoke_web_ai.py", "scripts/package_web.py",
]
FOLDERS = ["web", "api", "src/feedback_prd", "public", "evaluation", "tests"]


def main():
    selected = {ROOT / name for name in FILES}
    for folder in FOLDERS:
        selected.update(path for path in (ROOT / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    archive = ROOT / "output/web/feedback-lens-vercel-source.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(selected):
            if path.is_file():
                bundle.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert ".env" not in names
        assert not any(name.startswith(("output/", ".git/", ".vercel/", "node_modules/", ".venv/")) for name in names)
    print(f"Source archive: {len(names)} allowlisted files; credentials and local artifacts excluded.")


if __name__ == "__main__":
    main()
