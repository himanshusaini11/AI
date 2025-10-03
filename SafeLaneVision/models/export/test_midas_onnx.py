import os
import time

import pytest

np = pytest.importorskip("numpy")
ort = pytest.importorskip("onnxruntime")

onnx_path = "models/export/midas_small.onnx"  # or midas_small_int8.onnx

if not os.path.exists(onnx_path):
    pytest.skip("MiDaS export not available", allow_module_level=True)


def test_midas_inference_runs():
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    shape = [d if isinstance(d, int) else 256 for d in inp.shape]
    x = np.random.rand(*shape).astype(np.float32)

    sess.run(None, {"input": x})  # warm-up

    t0 = time.time()
    out = sess.run(None, {"input": x})
    ms = (time.time() - t0) * 1000
    assert out[0].shape[0] == shape[0]
    print(f"OK depth shape={out[0].shape}  {ms:.2f} ms")
