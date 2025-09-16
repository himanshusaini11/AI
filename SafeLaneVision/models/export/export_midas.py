import torch, onnx
m = torch.hub.load("intel-isl/MiDaS","MiDaS_small").eval()
x = torch.randn(1,3,256,256)
onnx_path = "models/export/midas_small.onnx"
torch.onnx.export(m, x, onnx_path, opset_version=17, input_names=["input"], output_names=["depth"])
print("saved:", onnx_path)