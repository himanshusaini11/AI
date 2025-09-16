from onnxruntime.quantization import quantize_dynamic, QuantType
import pathlib

targets = [
    "models/export/owlvit.onnx",
    "models/export/midas_small.onnx",
    "models/export/deeplab_mnv3.onnx",
]
for p in targets:
    out = str(pathlib.Path(p).with_suffix("").as_posix()) + "_int8.onnx"
    try:
        quantize_dynamic(p, out, weight_type=QuantType.QInt8)
        print("quantized:", out)
    except Exception as e:
        print("quant warn:", p, e)