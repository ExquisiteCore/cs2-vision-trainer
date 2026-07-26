from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_app_local_example_owns_paths_and_uses_safe_runtime_lifecycle():
    content = _read("examples/runtime_app_local.py")

    for token in (
        "from rp2350_hid_bridge import HidSession",
        "from cs2_vision_runtime import VisionRuntime",
        "VisionRuntime.from_app_dir",
        "vision.attach_hid_session",
        "board.native_handle",
        "hid_dll_path=board.dll_path",
        "board.stop_all()",
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
    assert "runtime.stop_all()" not in content
    assert "set_hid_port" not in content
    assert "from cs2_vision_runtime import HidSession" not in content
    assert "hid_session=" not in content


def test_live_example_shares_one_caller_owned_hid_session():
    content = _read("examples/runtime_live_move.py")

    for token in (
        "from rp2350_hid_bridge import HidSession",
        "from cs2_vision_runtime import VisionRuntime",
        "VisionRuntime.from_app_dir",
        "vision.attach_hid_session",
        "board.native_handle",
        "hid_dll_path=board.dll_path",
        "with vision.armed_output",
        "board.stop_all()",
        "process_next()",
    ):
        assert token in content

    assert "runtime.stop_all()" not in content
    assert "set_hid_port" not in content
    assert "from cs2_vision_runtime import HidSession" not in content
    assert "hid_session=" not in content


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
        "from rp2350_hid_bridge import HidSession",
        "from cs2_vision_runtime import VisionRuntime",
        "VisionRuntime.from_app_dir",
        "runtime-manifest.json",
        "resources/vision-runtime",
        "vision_runtime.dll",
        "rp2350_hid_bridge.dll",
        "vision.attach_hid_session",
        "board.native_handle",
        "hid_dll_path=board.dll_path",
        "board.stop_all()",
        "一个 COM 口",
        "两个独立 Python SDK",
        "零依赖",
        "主控拥有",
        "process_next()",
        "同步",
        "线程",
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
    assert "from cs2_vision_runtime import HidSession" not in content
    assert "hid_session=" not in content
    assert "runtime.stop_all()" not in content


def test_public_docs_keep_hid_middleware_owned_by_the_controller():
    for relative in (
        "README.md",
        "docs/BUILD.md",
        "docs/USAGE.md",
        "tools/cpp_analyzer/packaging/sm61/package/README_中文.md",
    ):
        content = _read(relative)
        for token in (
            "native_handle",
            "hid_dll_path",
            "board.stop_all()",
            "零依赖",
            "主控",
        ):
            assert token in content, f"{relative} must contain {token}"
        assert "from cs2_vision_runtime import HidSession" not in content
        assert "hid_session=" not in content
        assert "runtime.stop_all()" not in content


def test_top_level_docs_link_to_the_complete_python_sdk_guide():
    link = "docs/PYTHON_RUNTIME_SDK_INTEGRATION.md"
    readme = _read("README.md")
    usage = _read("docs/USAGE.md")
    build = _read("docs/BUILD.md")

    assert link in readme
    assert "PYTHON_RUNTIME_SDK_INTEGRATION.md" in usage
    assert "rp2350_hid_bridge.dll" in readme
    assert "rp2350_hid_bridge.dll" in usage
    assert "rp2350_hid_bridge.dll" in build
    assert "2048 counts" not in readme
    assert "2048 counts" not in usage


def test_partner_controller_guide_is_a_complete_standalone_integration_contract():
    content = _read("docs/PARTNER_CONTROLLER_INTEGRATION.md")

    for token in (
        "Python 主控",
        "vision_runtime.dll",
        "rp2350_hid_bridge.dll",
        "resources/vision-runtime",
        "cs2_vision_runtime_sdk-0.3.0",
        "rp2350_hid_bridge-0.2.0",
        "两个独立 Python SDK",
        "不要手工调用 ctypes.CDLL",
        "from rp2350_hid_bridge import HidSession",
        "from cs2_vision_runtime import VisionRuntime",
        "with HidSession",
        "app_dir=app_dir",
        "VisionRuntime.from_app_dir",
        "vision.attach_hid_session",
        "board.native_handle",
        "hid_dll_path=board.dll_path",
        "board.stop_all()",
        "process_next()",
        "同步",
        "线程",
        "GIL",
        "PyInstaller",
        "Nuitka",
        "RuntimeLoadError",
        "RuntimeCompatibilityError",
        "RuntimeCallError",
        "RuntimeStateError",
        "接入验收清单",
    ):
        assert token in content

    assert "from cs2_vision_runtime import HidSession" not in content
    assert "hid_session=" not in content
    assert "runtime.stop_all()" not in content
