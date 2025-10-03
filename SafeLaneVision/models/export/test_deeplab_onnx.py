import os
import time

import pytest

np = pytest.importorskip("numpy")
ort = pytest.importorskip("onnxruntime")

onnx_path = "models/export/deeplab_mnv3.onnx"  # or deeplab_mnv3_int8.onnx

if not os.path.exists(onnx_path):
    pytest.skip("DeepLab export not available", allow_module_level=True)


def test_deeplab_inference_runs():
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    shape = [d if isinstance(d, int) else 512 for d in sess.get_inputs()[0].shape]
    x = np.random.rand(*shape).astype(np.float32)

    sess.run(None, {"input": x})

    t0 = time.time()
    out = sess.run(None, {"input": x})
    ms = (time.time() - t0) * 1000
    assert out[0].shape[0] == shape[0]
    print(f"OK logits shape={out[0].shape}  {ms:.2f} ms")
