import torch, onnx
from transformers import OwlViTForObjectDetection

mname = "google/owlvit-base-patch16"
m = OwlViTForObjectDetection.from_pretrained(mname).eval()

# OWL-ViT expects image + tokenized text; we export both paths
dummy_img = torch.randn(1, 3, 768, 768)
# OWL-ViT text encoder expects 2D [batch, seq_len]
seq_len = 16
dummy_ids = torch.ones(1, seq_len, dtype=torch.long)
dummy_mask = torch.ones(1, seq_len, dtype=torch.long)

class Wrapper(torch.nn.Module):
    def __init__(self, m): 
        super().__init__(); self.m = m
    def forward(self, pixel_values, input_ids, attention_mask):
        out = self.m(pixel_values=pixel_values, input_ids=input_ids, attention_mask=attention_mask)
        return out["logits"], out["pred_boxes"]

w = Wrapper(m)
onnx_path = "models/export/owlvit.onnx"
torch.onnx.export(
    w, (dummy_img, dummy_ids, dummy_mask), onnx_path,
    input_names=["pixel_values","input_ids","attention_mask"],
    output_names=["logits","boxes"],
    dynamic_axes={
        "pixel_values": {0: "b"},
        "input_ids": {0: "b", 1: "seq"},
        "attention_mask": {0: "b", 1: "seq"},
    },
    opset_version=17
)
print("saved:", onnx_path)