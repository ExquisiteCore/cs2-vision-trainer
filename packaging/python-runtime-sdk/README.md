# CS2 Vision Runtime Python SDK

This wheel contains only the zero-dependency Python wrapper for
`vision_runtime.dll`. Controller applications install the independent
`rp2350-hid-bridge` wheel separately when they need physical HID control.
Neither wheel embeds native binaries. The DLLs, model, schema, TensorRT, CUDA,
cuDNN and other native runtime files are deployed separately in the documented
app-local layout.

See `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md` in the source repository for the
complete integration and release procedure.
