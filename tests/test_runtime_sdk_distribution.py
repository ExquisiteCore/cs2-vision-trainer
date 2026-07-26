import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build_python_runtime_sdk.ps1"


def _build_wheels(tmp_path: Path) -> dict[str, Path]:
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
    wheels = {
        wheel.name.split("-", 1)[0].lower(): wheel
        for wheel in output_dir.glob("*.whl")
    }
    assert set(wheels) == {
        "cs2_vision_runtime_sdk",
        "rp2350_hid_bridge",
    }
    return wheels


def test_runtime_sdk_wheels_have_coordinated_versions_and_dependencies(tmp_path):
    wheels = _build_wheels(tmp_path)
    source_files = {
        path.relative_to(PROJECT_ROOT / "src").as_posix()
        for path in (PROJECT_ROOT / "src" / "cs2_vision_runtime").glob("*.py")
    }
    hid_source_root = (
        PROJECT_ROOT
        / "tools"
        / "rp2350_keymouse_bridge_firmware"
        / "sdk"
        / "python"
    )
    hid_source_files = {
        path.relative_to(hid_source_root).as_posix()
        for path in (hid_source_root / "rp2350_hid_bridge").glob("*.py")
    }

    metadata_by_project = {}
    names_by_project = {}
    for project, wheel in wheels.items():
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            metadata_name = next(
                name for name in names if name.endswith(".dist-info/METADATA")
            )
            metadata_by_project[project] = archive.read(metadata_name).decode("utf-8")
            names_by_project[project] = names

    runtime_metadata = metadata_by_project["cs2_vision_runtime_sdk"]
    hid_metadata = metadata_by_project["rp2350_hid_bridge"]
    assert source_files <= names_by_project["cs2_vision_runtime_sdk"]
    assert hid_source_files <= names_by_project["rp2350_hid_bridge"]
    assert "Name: cs2-vision-runtime-sdk" in runtime_metadata
    assert "Version: 0.3.0" in runtime_metadata
    assert "Requires-Dist: rp2350-hid-bridge==0.2.0" in runtime_metadata
    assert "Version: 0.2.0" in hid_metadata
    assert "Requires-Dist: pyserial" not in hid_metadata
    for names in names_by_project.values():
        assert not any(
            name.lower().endswith((".dll", ".onnx", ".engine", ".exe"))
            or "/cuda" in name.lower()
            or "/cudnn" in name.lower()
            or "/tensorrt" in name.lower()
            for name in names
        )


def test_runtime_sdk_wheel_imports_in_clean_environment(tmp_path):
    wheels = _build_wheels(tmp_path)
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
            str(wheels["rp2350_hid_bridge"]),
            str(wheels["cs2_vision_runtime_sdk"]),
        ],
        cwd=tmp_path,
        check=True,
    )
    completed = subprocess.run(
        [
            str(venv_python),
            "-c",
            (
                "import cs2_vision_runtime as sdk; "
                "import rp2350_hid_bridge as hid; "
                "from cs2_vision_runtime import HidSession; "
                "assert HidSession is hid.HidSession; "
                "print(sdk.__version__, hid.__version__)"
            ),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "0.3.0 0.2.0"
