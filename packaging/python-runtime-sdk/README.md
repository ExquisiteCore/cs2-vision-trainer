# CS2 Vision Runtime Python SDK

This wheel contains the Python wrapper for `vision_runtime.dll` and depends on
the coordinated `rp2350-hid-bridge==0.2.0` Python wheel. Neither wheel embeds
native binaries. The DLLs, model, schema, TensorRT, CUDA, cuDNN and other native
runtime files are deployed separately in the documented app-local layout.

See `docs/PYTHON_RUNTIME_SDK_INTEGRATION.md` in the source repository for the
complete integration and release procedure.
