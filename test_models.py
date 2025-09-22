#!/usr/bin/env python3
"""Test which models actually work on HF Inference API"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

print("Testing available models on HuggingFace Inference API...")
print("=" * 50)

# Test different text generation models
text_models = [
    "gpt2",
    "distilgpt2",
    "EleutherAI/gpt-neo-125M",
    "google/flan-t5-small",
    "google/flan-t5-base",
    "microsoft/DialoGPT-small",
    "tiiuae/falcon-7b-instruct",
    "HuggingFaceH4/zephyr-7b-beta"
]

print("\n📝 Testing Text Generation Models:")
for model in text_models:
    url = f"https://api-inference.huggingface.co/models/{model}"
    try:
        response = requests.post(
            url,
            headers=headers,
            json={"inputs": "What is diabetes?", "parameters": {"max_new_tokens": 50}},
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ {model} - WORKING")
        elif response.status_code == 503:
            print(f"⏳ {model} - Model loading (503)")
        else:
            print(f"❌ {model} - Error {response.status_code}")
    except Exception as e:
        print(f"❌ {model} - Failed: {str(e)[:50]}")

# Test embedding models
print("\n🔢 Testing Embedding Models:")
embedding_models = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "BAAI/bge-small-en-v1.5"
]

for model in embedding_models:
    url = f"https://api-inference.huggingface.co/models/{model}"
    try:
        response = requests.post(
            url,
            headers=headers,
            json={"inputs": "test sentence"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ {model} - WORKING")
        elif response.status_code == 503:
            print(f"⏳ {model} - Model loading (503)")
        else:
            print(f"❌ {model} - Error {response.status_code}")
    except Exception as e:
        print(f"❌ {model} - Failed: {str(e)[:50]}")

print("\n" + "=" * 50)
print("Models marked with ✅ are immediately available")
print("Models marked with ⏳ need to be loaded (wait 20-30s)")