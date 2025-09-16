import torch, torchvision, onnx
m = torchvision.models.segmentation.deeplabv3_mobilenet_v3_large(weights="DEFAULT").eval()
x = torch.randn(1,3,512,512)
onnx_path = "models/export/deeplab_mnv3.onnx"
torch.onnx.export(m, x, onnx_path, opset_version=17, input_names=["input"], output_names=["logits"])
print("saved:", onnx_path)