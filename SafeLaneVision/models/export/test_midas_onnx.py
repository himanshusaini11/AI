import time, numpy as np, onnxruntime as ort

onnx_path = "models/export/midas_small.onnx"          # or midas_small_int8.onnx
sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

inp = sess.get_inputs()[0]
# Build a dummy input that matches the model’s shape, e.g. (1,3,256,256)
shape = [d if isinstance(d, int) else 256 for d in inp.shape]
x = np.random.rand(*shape).astype(np.float32)

# Warm-up
sess.run(None, {"input": x})

# Timed
t0 = time.time()
out = sess.run(None, {"input": x})
ms = (time.time() - t0) * 1000
print(f"OK depth shape={out[0].shape}  {ms:.2f} ms")