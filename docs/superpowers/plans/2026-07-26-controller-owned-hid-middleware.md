# Controller-Owned HID Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Python-level dependency between the vision SDK and the RP2350 SDK while preserving one controller-owned native HID session shared with `vision_runtime.dll` through an explicit opaque handle.

**Architecture:** The controller imports the two Python SDKs independently, opens `HidSession`, and injects its `native_handle` plus `dll_path` into `VisionRuntime`. The vision Python wheel remains zero-dependency; `vision_runtime.dll` retains only the native `Rp2350HidSession*`. The app-local manifest continues to validate the native HID DLL but no longer owns the HID Python package version.

**Tech Stack:** Python 3.11+, ctypes, C++17 C ABI, PowerShell, uv, pytest/unittest, CMake, xmake, Windows app-local DLL loading.

---

## Existing branch topology

Continue in the already isolated worktree and feature branches:

```text
cs2-vision-trainer                       feature/shared-hid-session-host
tools/cpp_analyzer                       feature/shared-hid-session-runtime
tools/rp2350_hid_bridge_cpp              feature/shared-hid-session-native
tools/rp2350_keymouse_bridge_firmware    feature/shared-hid-session-firmware-links
  sdk/cpp                                detached at native SDK commit
  sdk/python                             feature/shared-hid-session-python
```

Do not reset the completed native session, C ABI, `va_attach_hid_session`, packaging, or disarm work. This plan changes only the ownership boundary introduced above those layers.

## File and responsibility map

### RP2350 Python SDK

- Modify `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/client.py`: expose public read-only native handle and DLL path; remove the vision-specific private binding object.
- Modify `tools/rp2350_keymouse_bridge_firmware/sdk/python/tests/test_sdk.py`: verify public properties and closed-session errors.

### Vision Python SDK

- Modify `src/cs2_vision_runtime/runtime.py`: accept raw handle/path, keep only a native-attached boolean, and remove `hid_session` from `from_app_dir`.
- Modify `src/cs2_vision_runtime/__init__.py`: stop importing/re-exporting `HidSession`.
- Modify `tests/test_vision_runtime_sdk.py`: test the raw boundary and prove no concrete HID Python object is required.

### Manifest and Python distribution

- Modify `src/cs2_vision_runtime/package.py`: retain native HID DLL hash/ABI validation, remove HID Python version import and fields.
- Modify `tests/test_runtime_package.py`: manifest v2 fixture contains native HID DLL only.
- Modify `pyproject.toml` and `uv.lock`: move the local RP2350 Python package to the aggregate project's `dev` extra only.
- Modify `packaging/python-runtime-sdk/pyproject.toml`: restore zero runtime dependencies.
- Modify `packaging/python-runtime-sdk/README.md`: document the independent middleware SDK.
- Modify `scripts/build_python_runtime_sdk.ps1`: build only the vision SDK wheel.
- Modify `tests/test_runtime_sdk_distribution.py`: verify one zero-dependency vision wheel imports without the RP2350 package installed.

### Packaging, examples, and docs

- Modify `tools/cpp_analyzer/packaging/sm61/build-app-local-package.ps1`: remove HID Python SDK version fields from manifest v2 while retaining native DLL metadata.
- Modify `tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1`: assert the native-only manifest boundary.
- Modify `examples/runtime_live_move.py` and `examples/runtime_app_local.py`: independently import both SDKs and call raw attach.
- Modify `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`, `README.md`, `docs/BUILD.md`, `docs/USAGE.md`, and package README: document controller ownership.
- Modify `tests/test_runtime_sdk_docs.py`: enforce the decoupled usage contract.

## Stable interfaces after this correction

```python
# rp2350-hid-bridge-python
board.native_handle: int
board.dll_path: pathlib.Path

# cs2-vision-runtime-sdk
vision.attach_hid_session(
    native_handle: int,
    *,
    hid_dll_path: str | os.PathLike[str],
) -> None
```

Versions remain unchanged:

```text
rp2350_hid_bridge.dll ABI     1.0
rp2350_hid_bridge Python      0.2.0
vision_runtime.dll ABI        2.1
cs2-vision-runtime-sdk        0.3.0
manifest_version              2
```

### Task 1: Expose a controller-facing native session handle

**Files:**
- Modify: `tools/rp2350_keymouse_bridge_firmware/sdk/python/rp2350_hid_bridge/client.py`
- Test: `tools/rp2350_keymouse_bridge_firmware/sdk/python/tests/test_sdk.py`

- [ ] **Step 1: Replace the private vision binding test with public property tests**

In `test_context_shares_one_handle_and_releases_once`, replace `_binding_for_runtime()` assertions with:

```python
with hid:
    self.assertEqual(hid.native_handle, 123)
    self.assertEqual(hid.dll_path, api.path)

self.assertEqual(api.released, [123])
with self.assertRaisesRegex(RuntimeError, "closed"):
    _ = hid.native_handle
self.assertEqual(hid.dll_path, api.path)
```

Delete tests and helpers that mention `_NativeSessionBinding` or `_binding_for_runtime`.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
Push-Location tools\rp2350_keymouse_bridge_firmware\sdk\python
uv run python -m unittest `
  tests.test_sdk.HidSessionTests.test_context_shares_one_handle_and_releases_once -v
Pop-Location
```

Expected: FAIL because `HidSession.native_handle` and `dll_path` do not exist.

- [ ] **Step 3: Implement public read-only properties and remove the vision binding type**

Remove `_NativeSessionBinding` and `_binding_for_runtime()`. Add to `HidSession`:

```python
@property
def native_handle(self) -> int:
    with self._lock:
        handle = self._require_handle()
        if not self._api.is_open(handle):
            raise RuntimeError("RP2350 HID session is closed")
        return int(handle)

@property
def dll_path(self) -> Path:
    return Path(self._api.path).resolve()
```

These properties expose values only; they do not import or reference the vision SDK.

- [ ] **Step 4: Run all RP2350 Python SDK tests**

```powershell
Push-Location tools\rp2350_keymouse_bridge_firmware\sdk\python
uv run python -m unittest discover -s tests -v
Pop-Location
```

Expected: 18 tests pass and no test mentions `_binding_for_runtime`.

- [ ] **Step 5: Commit and push the independent controller properties**

```powershell
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python add `
  rp2350_hid_bridge\client.py tests\test_sdk.py
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python commit `
  -m "feat: expose native HID session identity"
git -C tools\rp2350_keymouse_bridge_firmware\sdk\python push
```

### Task 2: Make VisionRuntime accept only raw native values

**Files:**
- Modify: `src/cs2_vision_runtime/runtime.py`
- Modify: `src/cs2_vision_runtime/__init__.py`
- Test: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: Rewrite tests around a raw handle and path**

Delete `FakeHidSession`, weak-reference ownership assertions, and the public re-export assertion. Add:

```python
def test_raw_hid_attachment_is_ready_only_and_survives_reset():
    errors = importlib.import_module("cs2_vision_runtime.errors")
    api = FakeApi()
    runtime = VisionRuntime(_api=api)
    hid_dll = api.path.parent / "rp2350_hid_bridge.dll"

    runtime.attach_hid_session(456, hid_dll_path=hid_dll)
    assert api.calls[-1] == ("attach_hid_session", 456)

    with pytest.raises(errors.RuntimeStateError, match="attached HID session"):
        runtime.set_hid_port("COM4")

    runtime.open_video("videos/02.mp4", dry_run=True)
    runtime.reset()
    assert runtime._hid_attached is True
    runtime.close()


@pytest.mark.parametrize("handle", [0, None])
def test_raw_hid_attachment_rejects_empty_handle(handle):
    errors = importlib.import_module("cs2_vision_runtime.errors")
    runtime = VisionRuntime(_api=FakeApi())
    with pytest.raises(errors.RuntimeStateError, match="non-zero"):
        runtime.attach_hid_session(
            handle,
            hid_dll_path=Path("C:/app/rp2350_hid_bridge.dll"),
        )


def test_raw_hid_attachment_rejects_different_dll_before_native_call(tmp_path):
    errors = importlib.import_module("cs2_vision_runtime.errors")
    api = FakeApi()
    runtime = VisionRuntime(_api=api)
    calls_before = list(api.calls)
    with pytest.raises(errors.RuntimeCompatibilityError, match="must match"):
        runtime.attach_hid_session(
            456,
            hid_dll_path=tmp_path / "rp2350_hid_bridge.dll",
        )
    assert api.calls == calls_before
```

Change `test_runtime_from_app_dir_loads_package_and_configures_model` to call `from_app_dir(app_dir, data_dir=data_dir)` with no HID object and assert no `attach_hid_session` DLL call occurs.

Change the public package test to:

```python
assert not hasattr(package, "HidSession")
assert package.__version__ == "0.3.0"
```

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
uv run --extra dev pytest tests\test_vision_runtime_sdk.py -q
```

Expected: failures show the old method requires an object with `_binding_for_runtime`, `from_app_dir` still accepts `hid_session`, and `HidSession` is still re-exported.

- [ ] **Step 3: Implement the raw attach boundary**

In `VisionRuntime.__init__`, replace `self._hid_session = None` with:

```python
self._hid_attached = False
```

Restore the app-local factory signature:

```python
@classmethod
def from_app_dir(
    cls,
    app_dir: str | os.PathLike[str],
    *,
    data_dir: str | os.PathLike[str],
) -> "VisionRuntime":
```

Do not inspect or attach any HID object inside the factory.

Replace the public attach method with:

```python
def attach_hid_session(
    self,
    native_handle: int,
    *,
    hid_dll_path: str | os.PathLike[str],
) -> None:
    self._require_state("attach HID session", RuntimeState.READY)
    if native_handle is None or int(native_handle) == 0:
        raise RuntimeStateError("HID native handle must be non-zero")

    expected_hid_dll = (
        self._runtime_package.hid_dll_path
        if self._runtime_package is not None
        else (self._api.path.parent / "rp2350_hid_bridge.dll").resolve()
    )
    actual_hid_dll = Path(hid_dll_path).resolve()
    if actual_hid_dll != expected_hid_dll:
        raise RuntimeCompatibilityError(
            "HID session DLL must match the vision runtime directory: "
            f"expected {expected_hid_dll}, got {actual_hid_dll}"
        )

    self._check(
        self._api.attach_hid_session(
            self._require_handle(),
            int(native_handle),
        ),
        "attach HID session",
    )
    self._hid_attached = True
```

Replace every `_hid_session is not None` conflict check with `_hid_attached`. `close()` clears the boolean only after the native runtime has been destroyed. No Python HID object is retained.

- [ ] **Step 4: Remove the public HID import from the vision package**

Delete from `src/cs2_vision_runtime/__init__.py`:

```python
from rp2350_hid_bridge import HidSession
```

and remove `"HidSession"` from `__all__`.

- [ ] **Step 5: Run focused tests and verify GREEN**

```powershell
uv run --extra dev pytest tests\test_vision_runtime_sdk.py -q
```

Expected: all vision wrapper tests pass; `runtime.stop_all()` still rejects attached mode and directs the controller to its own middleware.

- [ ] **Step 6: Commit the decoupled vision Python API**

```powershell
git add src\cs2_vision_runtime\runtime.py `
  src\cs2_vision_runtime\__init__.py `
  tests\test_vision_runtime_sdk.py
git commit -m "refactor: accept raw controller-owned HID handles"
```

### Task 3: Keep native HID validation but remove Python package ownership from manifest

**Files:**
- Modify: `src/cs2_vision_runtime/package.py`
- Test: `tests/test_runtime_package.py`

- [ ] **Step 1: Change manifest tests to a native-only HID component**

In `make_app_layout`, use:

```python
"hid_bridge": {
    "dll": {
        "file_name": "rp2350_hid_bridge.dll",
        "sha256": _sha256(hid_dll),
        "abi_major": 1,
        "abi_minor": 0,
    },
},
```

Remove assertions for `hid_python_sdk_minimum` and `hid_python_sdk_recommended`. Delete the test mutating `hid_bridge.python_sdk.minimum`. Add:

```python
def test_runtime_package_loads_without_rp2350_python_package_import(tmp_path):
    from cs2_vision_runtime.package import RuntimePackage

    app_dir, data_dir, _ = make_app_layout(tmp_path)
    package = RuntimePackage.load(app_dir, data_dir)
    assert package.hid_dll_path.name == "rp2350_hid_bridge.dll"
    assert package.hid_abi_major == 1
    assert package.hid_abi_minor == 0
```

- [ ] **Step 2: Run package tests and verify RED**

```powershell
uv run --extra dev pytest tests\test_runtime_package.py -q
```

Expected: valid fixture fails because the loader still requires `hid_bridge.python_sdk` and imports `rp2350_hid_bridge.__version__`.

- [ ] **Step 3: Remove HID Python version fields and imports**

Delete:

```python
from rp2350_hid_bridge import __version__ as hid_sdk_version
```

Remove these `RuntimePackage` fields:

```python
hid_python_sdk_minimum: str
hid_python_sdk_recommended: str
```

Delete the entire `hid_bridge.python_sdk` validation block. Keep the file-name containment check, SHA256 validation, and exact ABI 1.0 requirement.

- [ ] **Step 4: Run package and vision tests**

```powershell
uv run --extra dev pytest `
  tests\test_runtime_package.py `
  tests\test_vision_runtime_sdk.py -q
```

Expected: both modules pass without importing the RP2350 Python package from `cs2_vision_runtime`.

- [ ] **Step 5: Commit the native-only runtime contract**

```powershell
git add src\cs2_vision_runtime\package.py tests\test_runtime_package.py
git commit -m "refactor: keep HID Python ownership outside vision manifest"
```

### Task 4: Restore an independent zero-dependency vision wheel

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `packaging/python-runtime-sdk/pyproject.toml`
- Modify: `packaging/python-runtime-sdk/README.md`
- Modify: `scripts/build_python_runtime_sdk.ps1`
- Test: `tests/test_runtime_sdk_distribution.py`

- [ ] **Step 1: Change distribution tests to expect one independent wheel**

Replace `_build_wheels` with:

```python
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
```

The metadata test must assert:

```python
assert "Name: cs2-vision-runtime-sdk" in metadata
assert "Version: 0.3.0" in metadata
assert "Requires-Python: >=3.11" in metadata
assert "Requires-Dist:" not in metadata
```

The clean-environment test installs only that wheel with `--no-deps`, then runs:

```python
import cs2_vision_runtime as sdk
assert not hasattr(sdk, "HidSession")
print(sdk.__version__)
```

Expected stdout: `0.3.0`.

- [ ] **Step 2: Run distribution tests and verify RED**

```powershell
uv run --extra dev pytest tests\test_runtime_sdk_distribution.py -q
```

Expected: failures because the builder emits two wheels and the runtime wheel declares `rp2350-hid-bridge==0.2.0`.

- [ ] **Step 3: Remove the runtime distribution dependency**

Delete from `packaging/python-runtime-sdk/pyproject.toml`:

```toml
dependencies = ["rp2350-hid-bridge==0.2.0"]
```

Update its README to state:

```markdown
This wheel contains only the zero-dependency Python wrapper for
`vision_runtime.dll`. Controller applications install the independent
`rp2350-hid-bridge` wheel separately when they need physical HID control.
```

- [ ] **Step 4: Restore the one-wheel build script**

Remove `$hidProjectRoot`, `$hidVersionFile`, the HID version parser, the HID `uv build` call, and HID wheel counting from `scripts/build_python_runtime_sdk.ps1`. Keep exactly:

```powershell
& uv build --wheel --out-dir $outputFullPath $stageRoot
if ($LASTEXITCODE -ne 0) {
    throw "uv build failed with exit code $LASTEXITCODE"
}

$wheel = @(
    Get-ChildItem -LiteralPath $outputFullPath `
        -Filter "cs2_vision_runtime_sdk-$sdkVersion-*.whl"
)
if ($wheel.Count -ne 1) {
    throw "Expected exactly one SDK wheel for version $sdkVersion in $outputFullPath"
}
```

- [ ] **Step 5: Move the local board SDK to aggregate development only**

Remove `rp2350-hid-bridge==0.2.0` from root `[project].dependencies`. Add it to `[project.optional-dependencies].dev`:

```toml
dev = [
    "pytest>=8.2",
    "rp2350-hid-bridge==0.2.0",
]
```

Keep the existing local `[tool.uv.sources]` entry so repository examples and integration tests can install both SDKs explicitly under `--extra dev`.

Run:

```powershell
uv lock
```

Expected: the root lock marks the local RP2350 SDK only under the `dev` extra; the standalone vision wheel metadata remains dependency-free.

- [ ] **Step 6: Run distribution tests and verify GREEN**

```powershell
uv run --extra dev pytest tests\test_runtime_sdk_distribution.py -q
```

Expected: one wheel builds, installs with `--no-deps`, and imports in an environment without `rp2350_hid_bridge`.

- [ ] **Step 7: Commit independent distribution metadata**

```powershell
git add pyproject.toml uv.lock `
  packaging\python-runtime-sdk `
  scripts\build_python_runtime_sdk.ps1 `
  tests\test_runtime_sdk_distribution.py
git commit -m "build: publish vision SDK independently from HID middleware"
```

### Task 5: Update app-local manifest generation to native HID metadata only

**Files:**
- Modify: `tools/cpp_analyzer/packaging/sm61/build-app-local-package.ps1`
- Test: `tools/cpp_analyzer/packaging/sm61/tests/run-tests.ps1`

- [ ] **Step 1: Remove HID Python version assertions from packaging tests**

Delete:

```powershell
Assert-Equal '0.2.0' $manifest.hid_bridge.python_sdk.minimum 'minimum HID Python SDK version'
Assert-Equal '0.2.0' $manifest.hid_bridge.python_sdk.recommended 'recommended HID Python SDK version'
```

Add:

```powershell
Assert-True `
    ($null -eq $manifest.hid_bridge.python_sdk) `
    'vision runtime manifest must not own the HID Python SDK version'
```

Keep all assertions for `rp2350_hid_bridge.dll`, SHA256, ABI 1.0, exactly two root DLLs, and the 36-character runtime hash suffix.

- [ ] **Step 2: Run packaging tests and verify RED**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools\cpp_analyzer\packaging\sm61\tests\run-tests.ps1 `
  -PythonProjectRoot (Resolve-Path '.').Path
```

Expected: the app-local test fails because `hid_bridge.python_sdk` is still emitted.

- [ ] **Step 3: Emit a native-only HID manifest object**

Use this exact object in `build-app-local-package.ps1`:

```powershell
hid_bridge = [pscustomobject][ordered]@{
    dll = [pscustomobject][ordered]@{
        file_name = 'rp2350_hid_bridge.dll'
        sha256 = $hidDllHash
        abi_major = 1
        abi_minor = 0
    }
}
```

Do not change native artifact copying or the portable diagnostic Python package aggregation.

- [ ] **Step 4: Run packaging tests and verify GREEN**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools\cpp_analyzer\packaging\sm61\tests\run-tests.ps1 `
  -PythonProjectRoot (Resolve-Path '.').Path
```

Expected: all 29 packaging tests pass.

- [ ] **Step 5: Commit and push the native-only manifest change**

```powershell
git -C tools\cpp_analyzer add packaging\sm61
git -C tools\cpp_analyzer commit `
  -m "refactor: separate HID Python ownership from runtime manifest"
git -C tools\cpp_analyzer push
```

### Task 6: Rewrite examples and integration docs around controller orchestration

**Files:**
- Modify: `examples/runtime_live_move.py`
- Modify: `examples/runtime_app_local.py`
- Modify: `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md`
- Modify: `README.md`
- Modify: `docs/BUILD.md`
- Modify: `docs/USAGE.md`
- Modify: `tools/cpp_analyzer/packaging/sm61/package/README_中文.md`
- Test: `tests/test_runtime_sdk_docs.py`
- Test: `tests/test_vision_runtime_sdk.py`

- [ ] **Step 1: Change docs tests to require independent imports and raw attach**

Require both examples and the guide to contain:

```text
from rp2350_hid_bridge import HidSession
from cs2_vision_runtime import VisionRuntime
board.native_handle
hid_dll_path=board.dll_path
vision.attach_hid_session
board.stop_all()
```

Require they do not contain:

```text
from cs2_vision_runtime import HidSession
hid_session=hid
runtime.stop_all()
```

Require the guide to explain that the two Python SDKs are independent and that the main controller owns the middleware.

- [ ] **Step 2: Run docs tests and verify RED**

```powershell
uv run --extra dev pytest `
  tests\test_runtime_sdk_docs.py `
  tests\test_vision_runtime_sdk.py -q
```

Expected: failures identify the old `cs2_vision_runtime.HidSession` import and object-level `hid_session=hid` factory parameter.

- [ ] **Step 3: Rewrite the live example lifecycle**

Use this exact orchestration shape in `runtime_live_move.py`:

```python
from rp2350_hid_bridge import HidSession
from cs2_vision_runtime import VisionRuntime

with HidSession(args.hid_port, app_dir=app_dir) as board:
    try:
        with VisionRuntime.from_app_dir(
            app_dir,
            data_dir=data_dir,
        ) as vision:
            vision.attach_hid_session(
                board.native_handle,
                hid_dll_path=board.dll_path,
            )
            profile = load_or_calibrate(
                vision,
                calibration_path,
                recalibrate=args.recalibrate,
                adapter=args.adapter,
                output=args.output,
            )
            vision.open_dxgi(
                adapter=args.adapter,
                output=args.output,
                player_side=args.player_side,
                dry_run=False,
            )
            with vision.armed_output(fire=args.click):
                process_loop(vision, args.show_every)
    finally:
        board.stop_all()
```

Apply the same independent imports and attach call in `runtime_app_local.py`. Its dry-run path creates neither `HidSession` nor native attachment.

- [ ] **Step 4: Rewrite public documentation**

All guides must state:

- the controller installs and imports two independent Python SDKs;
- `rp2350_hid_bridge.dll` is controller-owned middleware;
- vision receives only `native_handle + dll_path`;
- the vision wheel is zero-dependency;
- two app-local DLLs are native deployment requirements, not a Python package dependency;
- vision disarm preserves controller-held keyboard and mouse state;
- global release belongs to `board.stop_all()`.

The primary guide must retain the synchronous/threading explanation: `process_next()` is synchronous, ctypes releases the GIL, inference does not hold the HID lock, and request/ACK transactions serialize inside the middleware.

- [ ] **Step 5: Run docs, SDK, and syntax tests**

```powershell
uv run --extra dev pytest `
  tests\test_runtime_sdk_docs.py `
  tests\test_vision_runtime_sdk.py -q

uv run --extra dev python -c `
  "from pathlib import Path; files=['examples/runtime_live_move.py','examples/runtime_app_local.py','examples/runtime_dxgi_dryrun.py']; [compile(Path(f).read_text(encoding='utf-8'), f, 'exec') for f in files]; print('examples_compile=ok')"
```

Expected: tests pass and output contains `examples_compile=ok`.

- [ ] **Step 6: Commit controller-facing examples and docs**

```powershell
git add README.md docs examples `
  tests\test_runtime_sdk_docs.py `
  tests\test_vision_runtime_sdk.py
git commit -m "docs: make the controller own HID middleware"
```

### Task 7: Synchronize gitlinks and run complete automated verification

**Files:**
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware/sdk/python`
- Update gitlink: `tools/rp2350_keymouse_bridge_firmware`
- Update gitlink: `tools/cpp_analyzer`
- Update gitlink: `tools/rp2350_hid_bridge_cpp` only if its HEAD changed

- [ ] **Step 1: Pin the firmware Python SDK gitlink**

```powershell
$pythonHead = git -C tools\rp2350_keymouse_bridge_firmware\sdk\python rev-parse HEAD
git -C tools\rp2350_keymouse_bridge_firmware add sdk/python
git -C tools\rp2350_keymouse_bridge_firmware commit `
  -m "chore: expose controller-owned HID session identity"
git -C tools\rp2350_keymouse_bridge_firmware push
```

Expected: firmware root changes only the `sdk/python` gitlink; native firmware source remains unchanged.

- [ ] **Step 2: Run native HID, Python SDK, and firmware tests**

```powershell
cmake -S tools\rp2350_hid_bridge_cpp `
  -B tools\rp2350_hid_bridge_cpp\build-controller-owned-final `
  -A x64
cmake --build tools\rp2350_hid_bridge_cpp\build-controller-owned-final `
  --config Release
ctest --test-dir tools\rp2350_hid_bridge_cpp\build-controller-owned-final `
  -C Release --output-on-failure

Push-Location tools\rp2350_keymouse_bridge_firmware\sdk\python
uv run python -m unittest discover -s tests -v
Pop-Location

cargo test `
  --manifest-path tools\rp2350_keymouse_bridge_firmware\Cargo.toml `
  --target x86_64-pc-windows-msvc --lib
```

Expected: three native CTest targets, 18 Python SDK tests, and 197 firmware tests pass.

- [ ] **Step 3: Run vision builds through both build systems**

```powershell
$hidRoot = (Resolve-Path 'tools\rp2350_hid_bridge_cpp').Path

cmake -S tools\cpp_analyzer `
  -B tools\cpp_analyzer\build-controller-owned-final `
  -A x64 `
  -DONNXRUNTIME_ROOT=D:\Tool\onnxruntime-win-x64-gpu-1.17.3 `
  -DHID_SDK_ROOT=$hidRoot
cmake --build tools\cpp_analyzer\build-controller-owned-final --config Release
ctest --test-dir tools\cpp_analyzer\build-controller-owned-final `
  -C Release --output-on-failure

Push-Location tools\cpp_analyzer
xmake f -c -m release `
  --onnxruntime_root=D:\Tool\onnxruntime-win-x64-gpu-1.17.3 `
  --hid_sdk_root=$hidRoot
xmake
Pop-Location
```

Expected: two vision CTest targets pass and xmake emits both native DLLs.

- [ ] **Step 4: Run the complete parent and packaging suites**

```powershell
uv sync --extra dev
uv run --extra dev pytest -q
powershell -NoProfile -ExecutionPolicy Bypass `
  -File tools\cpp_analyzer\packaging\sm61\tests\run-tests.ps1 `
  -PythonProjectRoot (Resolve-Path '.').Path
git diff --check
```

Expected: all parent tests and 29 packaging tests pass; `git diff --check` is silent.

- [ ] **Step 5: Commit exact parent gitlinks**

```powershell
git add tools\cpp_analyzer `
  tools\rp2350_keymouse_bridge_firmware `
  tools\rp2350_hid_bridge_cpp
git commit -m "refactor: decouple vision SDK from HID middleware"
git push
```

- [ ] **Step 6: Verify recursive equality and clean branches**

```powershell
$directCpp = git -C tools\rp2350_hid_bridge_cpp rev-parse HEAD
$nestedCpp = git -C tools\rp2350_keymouse_bridge_firmware\sdk\cpp rev-parse HEAD
$firmwareCpp = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD:sdk/cpp
$firmwarePython = git -C tools\rp2350_keymouse_bridge_firmware rev-parse HEAD:sdk/python
$nestedPython = git -C tools\rp2350_keymouse_bridge_firmware\sdk\python rev-parse HEAD
if ($directCpp -ne $nestedCpp -or $directCpp -ne $firmwareCpp) {
    throw 'C++ SDK gitlinks differ'
}
if ($firmwarePython -ne $nestedPython) {
    throw 'Python SDK gitlink differs'
}
git submodule status --recursive
git status --short --branch
```

Expected: recursive hashes agree and every feature branch is clean and pushed.

### Task 8: Hardware acceptance and main integration

**Files:**
- No source files unless hardware exposes a reproducible defect; every defect requires a failing automated test before correction.

- [ ] **Step 1: Build an app-local manifest-v2 payload**

```powershell
& .\tools\cpp_analyzer\packaging\sm61\build-app-local-package.ps1 `
  -PortablePackageRoot .\dist\cs2-vision-runtime-sm61 `
  -OutputRoot .\dist\MyClientRuntime `
  -PythonSdkVersion 0.3.0
```

Expected: exactly `vision_runtime.dll` and `rp2350_hid_bridge.dll` at the output root; manifest v2 contains native HID DLL hash/ABI but no `hid_bridge.python_sdk` object.

- [ ] **Step 2: Verify one COM and cached calibration**

```powershell
uv run --extra dev python .\examples\runtime_live_move.py `
  --app-dir .\dist\MyClientRuntime `
  --data-dir "$env:LOCALAPPDATA\ExquisiteCore\MyClient" `
  --hid-port COM4 `
  --player-side ct `
  --calibration-path .\hid-calibration.json `
  --enable-live-output `
  --show-every 1
```

Expected: COM4 opens once, cached calibration loads without camera movement, TensorRT initializes, and aim output works.

- [ ] **Step 3: Verify the controller can use keyboard and mouse independently**

Run a public-API acceptance script that performs:

```python
board.key_down("W")
board.mouse_move(5, 0)
with vision.armed_output(fire=False):
    for _ in range(30):
        vision.process_next()
time.sleep(1.0)
board.key_up("W")
board.stop_all()
```

Expected: W remains held during the one-second gap after vision disarm; controller mouse and vision mouse commands both execute; `board.stop_all()` releases everything immediately.

- [ ] **Step 4: Verify control-thread commands during synchronous inference**

Run `vision.process_next()` repeatedly in a worker thread while the controller thread alternates `board.key_down("W")` / `board.key_up("W")` and short mouse moves.

Expected: no duplicate COM open, timeout, sequence mismatch, corrupted response, or unintended global release.

- [ ] **Step 5: Invoke completion skills and merge in dependency order**

After hardware evidence passes, invoke:

```text
superpowers:verification-before-completion
superpowers:requesting-code-review
superpowers:finishing-a-development-branch
```

Merge and push in this order:

```text
1. rp2350-hid-bridge-python main
2. rp2350-hid-bridge-cpp main, only if changed
3. firmware main with final sdk/cpp and sdk/python gitlinks
4. cpp_analyzer main
5. parent cs2-vision-trainer main with final child gitlinks
```

After each child main merge, update the upper repository to the resulting main commit and rerun recursive gitlink equality. Do not delete feature branches until every remote `main` and recursive gitlink agrees.
