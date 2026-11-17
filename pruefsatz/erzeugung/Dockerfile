FROM pytorch/pytorch:2.14.1-cuda13.0-cudnn9-runtime
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --break-system-packages "transformers>=5.16.1,<6" "huggingface_hub>=1.31.0,<2.0" "accelerate>=1.0.0" "peft>=0.20.0"       "safetensors>=0.4.5" "sentencepiece>=0.2.0" "protobuf>=4.25" "Pillow>=10" "imageio>=2.37" "imageio-ffmpeg>=0.6" "setuptools>=84"       "git+https://github.com/Vimoo-AI/diffusers.git@6d0bfa301cd3ff919e5a261582704c1ae74696b0"
RUN git clone https://github.com/Vimoo-AI/Vimoo-1.0.git /vimoo && git -C /vimoo checkout df2ea2cbc0a4a21907f21adba3fa8c145f30902c
ENV PIP_BREAK_SYSTEM_PACKAGES=1 HF_HOME=/hf PYTHONUNBUFFERED=1
WORKDIR /arbeit
