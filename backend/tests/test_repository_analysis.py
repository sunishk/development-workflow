import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import repository_analysis_service as analysis_module
from app.services.repository_analysis_service import RepositoryAnalysisService


@pytest.fixture
def analyzer():
    return RepositoryAnalysisService()


def _workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        analysis_module.repository_service,
        "workspace_for_job",
        lambda job_id: SimpleNamespace(path=tmp_path),
    )


def test_detects_maven_spring_boot(monkeypatch, tmp_path, analyzer):
    _workspace(monkeypatch, tmp_path)
    (tmp_path / "pom.xml").write_text("<artifactId>spring-boot-starter-web</artifactId>")
    (tmp_path / "mvnw").write_text("")
    (tmp_path / "AGENTS.md").write_text("instructions")

    profile = analyzer.analyze(uuid4())

    assert profile.languages == ["Java"]
    assert profile.frameworks == ["Spring Boot"]
    assert profile.build_tool == "Maven"
    assert profile.test_command == ["./mvnw", "test"]
    assert profile.build_command == ["./mvnw", "package", "-DskipTests"]
    assert "AGENTS.md" in profile.instruction_files


def test_detects_nextjs_npm_scripts(monkeypatch, tmp_path, analyzer):
    _workspace(monkeypatch, tmp_path)
    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {"test": "vitest", "build": "next build"},
                "dependencies": {"next": "1", "react": "1"},
                "devDependencies": {"typescript": "1"},
            }
        )
    )

    profile = analyzer.analyze(uuid4())

    assert profile.languages == ["TypeScript"]
    assert profile.frameworks == ["Next.js", "React"]
    assert profile.package_manager == "npm"
    assert profile.install_command == ["npm", "ci"]
    assert profile.test_command == ["npm", "run", "test"]
    assert profile.build_command == ["npm", "run", "build"]


def test_detects_python(monkeypatch, tmp_path, analyzer):
    _workspace(monkeypatch, tmp_path)
    (tmp_path / "requirements.txt").write_text("pytest\n")

    profile = analyzer.analyze(uuid4())

    assert profile.languages == ["Python"]
    assert profile.install_command == ["python", "-m", "pip", "install", "-r", "requirements.txt"]
    assert profile.test_command == ["python", "-m", "pytest"]


@pytest.mark.parametrize(
    "marker,language,test_command,build_command",
    [
        ("go.mod", "Go", ["go", "test", "./..."], ["go", "build", "./..."]),
        ("Cargo.toml", "Rust", ["cargo", "test"], ["cargo", "build"]),
        ("app.csproj", "C#", ["dotnet", "test"], ["dotnet", "build", "--no-restore"]),
    ],
)
def test_detects_other_ecosystems(
    monkeypatch, tmp_path, analyzer, marker, language, test_command, build_command
):
    _workspace(monkeypatch, tmp_path)
    (tmp_path / marker).write_text("")

    profile = analyzer.analyze(uuid4())

    assert language in profile.languages
    assert profile.test_command == test_command
    assert profile.build_command == build_command
