import time, numpy as np, onnxruntime as ort

onnx_path = "models/export/deeplab_mnv3.onnx"         # or deeplab_mnv3_int8.onnx
sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

inp = sess.get_inputs()[0]
# Match dynamic/static dims automatically (fill symbolic dims with 512)
shape = [d if isinstance(d, int) else 512 for d in inp.shape]
x = np.random.rand(*shape).astype(np.float32)

# Warm-up
sess.run(None, {"input": x})

# Timed
t0 = time.time()
out = sess.run(None, {"input": x})
ms = (time.time() - t0) * 1000
print(f"OK logits shape={out[0].shape}  {ms:.2f} ms")