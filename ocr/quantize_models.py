"""
Standalone INT8 model quantisation script for Synaptix (Improvement #7).
Reduces server model size by 50-75% and latency by ~40% for 512 MB Render deployment.
"""

import os
from pathlib import Path
from onnxruntime.quantization import quantize_dynamic, QuantType

MODELS = [
    "ch_PP-OCRv4_server_det_infer.onnx",
    "ch_PP-OCRv4_server_rec_doc_infer.onnx",
]

os.makedirs("models/quantized", exist_ok=True)

for model in MODELS:
    src = f"models/{model}"
    dst = f"models/quantized/{model.replace('.onnx', '_int8.onnx')}"

    if not Path(src).exists():
        print(f"Skipping {src}: Source model not found in models/ directory.")
        print(f"Please download {model} into models/ before quantising.")
        continue

    print(f"Quantising {src} -> {dst} (INT8 dynamic)...")
    quantize_dynamic(
        model_input=src,
        model_output=dst,
        weight_type=QuantType.QInt8,
    )
    print(f"Quantized: {src} -> {dst}")
