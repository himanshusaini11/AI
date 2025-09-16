import time, numpy as np, onnxruntime as ort

def run(model_path, inputs, key_map, iters=50, warmup=10):
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    # Build feed with correct names
    feed = {k: inputs[v] for k, v in key_map.items()}
    for _ in range(warmup):
        sess.run(None, feed)
    t = 0.0
    for _ in range(iters):
        t0 = time.time()
        sess.run(None, feed)
        t += (time.time() - t0)
    return (t / iters) * 1000

# OWL-ViT
from PIL import Image
from transformers import OwlViTProcessor
proc = OwlViTProcessor.from_pretrained("google/owlvit-base-patch16")
img = Image.fromarray((np.random.rand(768,768,3)*255).astype(np.uint8))
enc = proc(text=["pothole"], images=img, return_tensors="np")
owl_inputs = {
    "pixel_values": enc["pixel_values"].astype(np.float32),
    "input_ids": enc["input_ids"].astype(np.int64),
    "attention_mask": enc["attention_mask"].astype(np.int64),
}
owl_keymap = {"pixel_values": "pixel_values", "input_ids": "input_ids", "attention_mask": "attention_mask"}
owl_keymap = {"pixel_values": "pixel_values", "input_ids": "input_ids", "attention_mask": "attention_mask"}
print("OWL-ViT fp32:", f"{run('models/export/owlvit.onnx', owl_inputs, owl_keymap):.2f} ms")
try:
    print("OWL-ViT int8:", f"{run('models/export/owlvit_int8.onnx', owl_inputs, owl_keymap):.2f} ms")
except Exception as e:
    print(f"OWL-ViT int8: skipped ({e.__class__.__name__})")

# MiDaS
# Infer input shape dynamically
def make_dummy(onnx_path, fill=256):
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    name, shape = sess.get_inputs()[0].name, sess.get_inputs()[0].shape
    shape = [d if isinstance(d,int) else fill for d in shape]
    x = np.random.rand(*shape).astype(np.float32)
    return {"input": x}

midas_in = make_dummy("models/export/midas_small.onnx", 256)
midas_keymap = {"input": "input"}
print("MiDaS fp32:", f"{run('models/export/midas_small.onnx', midas_in, midas_keymap):.2f} ms")
try:
    print("MiDaS int8:", f"{run('models/export/midas_small_int8.onnx', midas_in, midas_keymap):.2f} ms")
except Exception as e:
    print(f"MiDaS int8: skipped ({e.__class__.__name__})")

# DeepLab
deeplab_in = make_dummy("models/export/deeplab_mnv3.onnx", 512)
deeplab_keymap = {"input": "input"}
print("DeepLab fp32:", f"{run('models/export/deeplab_mnv3.onnx', deeplab_in, deeplab_keymap):.2f} ms")
try:
    print("DeepLab int8:", f"{run('models/export/deeplab_mnv3_int8.onnx', deeplab_in, deeplab_keymap):.2f} ms")
except Exception as e:
    print(f"DeepLab int8: skipped ({e.__class__.__name__})")