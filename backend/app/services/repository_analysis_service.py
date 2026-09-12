import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from app.services.repository_service import repository_service


@dataclass(frozen=True)
class RepositoryProfile:
    languages: list[str]
    frameworks: list[str]
    build_tool: str | None
    package_manager: str | None
    install_command: list[str] | None
    test_command: list[str] | None
    build_command: list[str] | None
    instruction_files: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class RepositoryAnalysisService:
    def analyze(self, job_id: UUID) -> RepositoryProfile:
        workspace = repository_service.workspace_for_job(job_id)
        if workspace is None:
            raise ValueError(f"Job {job_id} has no prepared workspace")

        root = workspace.path
        files = {path.name for path in root.iterdir() if path.is_file()}
        languages: list[str] = []
        frameworks: list[str] = []
        build_tool: str | None = None
        package_manager: str | None = None
        install_command: list[str] | None = None
        test_command: list[str] | None = None
        build_command: list[str] | None = None

        if "pom.xml" in files:
            languages.append("Java")
            build_tool = "Maven"
            mvn = "./mvnw" if (root / "mvnw").exists() else "mvn"
            test_command = [mvn, "test"]
            build_command = [mvn, "package", "-DskipTests"]
            if self._contains(root / "pom.xml", "spring-boot"):
                frameworks.append("Spring Boot")

        elif "build.gradle" in files or "build.gradle.kts" in files:
            languages.extend(["Java", "Kotlin"] if "build.gradle.kts" in files else ["Java"])
            build_tool = "Gradle"
            gradle = "./gradlew" if (root / "gradlew").exists() else "gradle"
            test_command = [gradle, "test"]
            build_command = [gradle, "build", "-x", "test"]

        if "package.json" in files:
            package_manager, install_command = self._node_package_manager(root, files)
            package_json = self._read_package_json(root / "package.json")
            scripts = package_json.get("scripts", {}) if isinstance(package_json, dict) else {}
            dependencies = {
                **(package_json.get("dependencies", {}) if isinstance(package_json, dict) else {}),
                **(package_json.get("devDependencies", {}) if isinstance(package_json, dict) else {}),
            }
            if "TypeScript" not in languages and "typescript" in dependencies:
                languages.append("TypeScript")
            elif "JavaScript" not in languages:
                languages.append("JavaScript")
            if "next" in dependencies:
                frameworks.append("Next.js")
            if "react" in dependencies:
                frameworks.append("React")
            if "test" in scripts:
                test_command = [package_manager, "run", "test"]
            if "build" in scripts:
                build_command = [package_manager, "run", "build"]

        if "pyproject.toml" in files or "requirements.txt" in files:
            if "Python" not in languages:
                languages.append("Python")
            build_tool = build_tool or "Python"
            if "requirements.txt" in files:
                install_command = ["python", "-m", "pip", "install", "-r", "requirements.txt"]
            elif "pyproject.toml" in files:
                install_command = ["python", "-m", "pip", "install", "-e", "."]
            test_command = test_command or ["python", "-m", "pytest"]

        if "go.mod" in files:
            languages.append("Go")
            build_tool = "Go"
            test_command = ["go", "test", "./..."]
            build_command = ["go", "build", "./..."]

        if "Cargo.toml" in files:
            languages.append("Rust")
            build_tool = "Cargo"
            test_command = ["cargo", "test"]
            build_command = ["cargo", "build"]

        if any(path.suffix in {".csproj", ".sln"} for path in root.iterdir() if path.is_file()):
            languages.append("C#")
            build_tool = ".NET"
            test_command = ["dotnet", "test"]
            build_command = ["dotnet", "build", "--no-restore"]

        instruction_files = [
            name
            for name in ["AGENTS.md", "CLAUDE.md", "README.md", "CONTRIBUTING.md"]
            if (root / name).is_file()
        ]

        return RepositoryProfile(
            languages=sorted(set(languages)),
            frameworks=sorted(set(frameworks)),
            build_tool=build_tool,
            package_manager=package_manager,
            install_command=install_command,
            test_command=test_command,
            build_command=build_command,
            instruction_files=instruction_files,
        )

    @staticmethod
    def _contains(path: Path, value: str) -> bool:
        try:
            return value.lower() in path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            return False

    @staticmethod
    def _read_package_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _node_package_manager(root: Path, files: set[str]) -> tuple[str, list[str]]:
        if "pnpm-lock.yaml" in files:
            return "pnpm", ["pnpm", "install", "--frozen-lockfile"]
        if "yarn.lock" in files:
            return "yarn", ["yarn", "install", "--frozen-lockfile"]
        if "bun.lockb" in files or "bun.lock" in files:
            return "bun", ["bun", "install", "--frozen-lockfile"]
        if "package-lock.json" in files:
            return "npm", ["npm", "ci"]
        return "npm", ["npm", "install"]


repository_analysis_service = RepositoryAnalysisService()
