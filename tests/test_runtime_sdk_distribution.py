import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_python_runtime_sdk.ps1"


def _build_wheel(tmp_path: Path) -> Path:
    output_dir = tmp_path / "dist"
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-OutputDir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    wheels = list(output_dir.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_runtime_sdk_wheel_is_zero_dependency_and_contains_only_python_sdk(tmp_path):
    wheel = _build_wheel(tmp_path)
    source_files = {
        path.relative_to(PROJECT_ROOT / "src").as_posix()
        for path in (PROJECT_ROOT / "src" / "cs2_vision_runtime").glob("*.py")
    }

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")

    assert source_files <= names
    assert "Name: cs2-vision-runtime-sdk" in metadata
    assert "Version: 0.2.0" in metadata
    assert "Requires-Python: >=3.11" in metadata
    assert "Requires-Dist:" not in metadata
    assert not any(
        name.lower().endswith((".dll", ".onnx", ".engine", ".exe"))
        or "/cuda" in name.lower()
        or "/cudnn" in name.lower()
        or "/tensorrt" in name.lower()
        for name in names
    )


def test_runtime_sdk_wheel_imports_in_clean_environment(tmp_path):
    wheel = _build_wheel(tmp_path)
    uv = shutil.which("uv")
    assert uv is not None
    venv = tmp_path / "venv"
    subprocess.run(
        [uv, "venv", str(venv), "--python", sys.executable],
        cwd=tmp_path,
        check=True,
    )
    venv_python = venv / "Scripts" / "python.exe"
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(venv_python),
            "--no-deps",
            str(wheel),
        ],
        cwd=tmp_path,
        check=True,
    )
    completed = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import cs2_vision_runtime as sdk; print(sdk.__version__)",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "0.2.0"
