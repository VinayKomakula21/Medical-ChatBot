#!/usr/bin/env python3
"""Test HuggingFace Inference API with proper endpoints"""
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

print("Testing HuggingFace Inference API...")
print("=" * 50)

# Test text generation with the serverless inference API
print("\n1. Testing Text Generation (GPT-2)...")
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# Try different API endpoints
models_to_test = [
    ("gpt2", "https://api-inference.huggingface.co/models/gpt2"),
    ("facebook/opt-125m", "https://api-inference.huggingface.co/models/facebook/opt-125m"),
    ("google/flan-t5-small", "https://api-inference.huggingface.co/models/google/flan-t5-small"),
]

for model_name, url in models_to_test:
    print(f"\nTesting {model_name}...")

    payload = {
        "inputs": "The definition of diabetes is",
        "parameters": {
            "max_new_tokens": 50,
            "temperature": 0.7
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success! Response: {json.dumps(result, indent=2)[:200]}...")
        elif response.status_code == 503:
            error_data = response.json()
            print(f"⏳ Model is loading. Estimated time: {error_data.get('estimated_time', 'unknown')} seconds")
        else:
            print(f"❌ Error: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Exception: {e}")

# Test feature extraction (embeddings)
print("\n" + "=" * 50)
print("2. Testing Feature Extraction (Embeddings)...")

embedding_url = "https://api-inference.huggingface.co/models/BAAI/bge-small-en-v1.5"
payload = {"inputs": "This is a test sentence for embeddings."}

try:
    response = requests.post(embedding_url, headers=headers, json=payload, timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            print(f"✅ Success! Embedding dimension: {len(result[0]) if isinstance(result[0], list) else len(result)}")
    else:
        print(f"❌ Error: {response.text[:200]}")
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n" + "=" * 50)
print("\nNOTE: If models show 503 (loading), wait 20-30 seconds and try again.")
print("The free tier has cold start times when models aren't cached.")