import time, numpy as np, onnxruntime as ort
from PIL import Image
from transformers import OwlViTProcessor

onnx_path = "models/export/owlvit.onnx"
mname = "google/owlvit-base-patch16"
processor = OwlViTProcessor.from_pretrained(mname)

# Dummy image (random). Replace with a real 768x768 image for a better test.
img = Image.fromarray((np.random.rand(768,768,3)*255).astype(np.uint8))

enc = processor(text=["pothole"], images=img, return_tensors="np")
inputs = {
    "pixel_values": enc["pixel_values"],            # (1,3,768,768)
    "input_ids": enc["input_ids"],                  # (1, seq)
    "attention_mask": enc["attention_mask"],        # (1, seq)
}

sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
# Warm-up
sess.run(None, inputs)
# Timed
t0 = time.time()
outs = sess.run(None, inputs)
dt = (time.time()-t0)*1000
logits, boxes = outs
print(f"OK  logits {logits.shape}  boxes {boxes.shape}  {dt:.2f} ms")