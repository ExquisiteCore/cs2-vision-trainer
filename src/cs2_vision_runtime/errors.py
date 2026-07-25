class VisionRuntimeError(RuntimeError):
    """Base error for the Python runtime SDK."""


class RuntimeLoadError(VisionRuntimeError):
    """The native runtime or one of its dependencies could not be loaded."""


class RuntimeCompatibilityError(VisionRuntimeError):
    """The Python SDK and native runtime are not ABI compatible."""


class RuntimeCallError(VisionRuntimeError):
    """A native runtime operation returned an error."""


class RuntimeStateError(VisionRuntimeError):
    """An operation was requested in an invalid runtime state."""
