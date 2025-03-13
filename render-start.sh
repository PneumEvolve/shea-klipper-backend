#!/bin/bash
pip install --no-cache-dir torch torchvision torchaudio
pip install --no-cache-dir openai-whisper ffmpeg
uvicorn main:app --host 0.0.0.0 --port 10000