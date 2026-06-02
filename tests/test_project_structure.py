from pathlib import Path


def test_required_project_structure_exists() -> None:
    root = Path(__file__).resolve().parents[1]

    required_paths = [
        "AGENTS.md",
        "README.md",
        "pyproject.toml",
        ".env.example",
        ".gitignore",
        "data/raw/.gitkeep",
        "data/processed/.gitkeep",
        "app/.gitkeep",
        "src/__init__.py",
        "src/ingestion/__init__.py",
        "src/semantic_layer/__init__.py",
        "src/templates/__init__.py",
        "src/templates/sql_templates/.gitkeep",
        "src/runtime/__init__.py",
        "src/validation/__init__.py",
        "src/evals/__init__.py",
        "src/observability/__init__.py",
        "tests/__init__.py",
        "tests/test_project_structure.py",
    ]

    missing = [path for path in required_paths if not (root / path).exists()]

    assert missing == []

