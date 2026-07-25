from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_app_local_example_owns_paths_and_uses_safe_runtime_lifecycle():
    content = _read("examples/runtime_app_local.py")

    for token in (
        "VisionRuntime.from_app_dir",
        "Path(sys.executable).resolve().parent",
        "--app-dir",
        "--data-dir",
        "--calibration-path",
        "--recalibrate",
        "--enable-live-output",
        "set_hid_calibration_path",
        "get_hid_calibration",
        "calibrate_hid",
        "armed_output",
        "iter_actions",
        "dry_run=not args.enable_live_output",
    ):
        assert token in content

    assert "CS2_VISION_RUNTIME_DLL" not in content


def test_dxgi_dryrun_supports_app_local_and_low_level_development_modes():
    content = _read("examples/runtime_dxgi_dryrun.py")

    assert "--app-dir" in content
    assert "--data-dir" in content
    assert "VisionRuntime.from_app_dir" in content
    assert "VisionRuntime()" in content
    assert "dry_run=True" in content
    assert "--hid-port" not in content


def test_python_runtime_sdk_guide_covers_frozen_client_contract():
    content = _read("docs/PYTHON_RUNTIME_SDK_INTEGRATION.md")

    for token in (
        "VisionRuntime.from_app_dir",
        "runtime-manifest.json",
        "resources/vision-runtime",
        "vision_runtime.dll",
        "uv",
        "PyInstaller",
        "Nuitka",
        "TensorRT",
        "DXGI dry-run",
        "set_hid_calibration_path",
        "get_hid_calibration",
        "calibrate_hid",
        "VisionAction",
        "armed_output",
        "RuntimeLoadError",
        "RuntimeCompatibilityError",
        "RuntimeCallError",
        "RuntimeStateError",
        "发布前检查清单",
    ):
        assert token in content

    assert "from_bundle" not in content


def test_top_level_docs_link_to_the_complete_python_sdk_guide():
    link = "docs/PYTHON_RUNTIME_SDK_INTEGRATION.md"
    readme = _read("README.md")
    usage = _read("docs/USAGE.md")

    assert link in readme
    assert "PYTHON_RUNTIME_SDK_INTEGRATION.md" in usage
    assert "2048 counts" not in readme
    assert "2048 counts" not in usage
