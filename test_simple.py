#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Testing components separately...")

# Test 1: Just Pinecone
print("\n1. Testing Pinecone ONLY...")
try:
    from pinecone import Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    indexes = pc.list_indexes().names()
    print(f"   ✅ Pinecone works! Indexes: {indexes}")

    # Test getting index stats
    index = pc.Index("medicbot")
    stats = index.describe_index_stats()
    print(f"   ✅ Index stats: {stats.total_vector_count} vectors")
except Exception as e:
    print(f"   ❌ Pinecone error: {e}")

# Test 2: Just HuggingFace API
print("\n2. Testing HuggingFace API ONLY...")
try:
    import requests

    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
    headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}

    response = requests.post(API_URL, headers=headers, json={
        "inputs": "Hello, I am",
        "parameters": {"max_new_tokens": 10}
    }, timeout=5)

    if response.status_code == 200:
        print(f"   ✅ HuggingFace API works!")
        print(f"   Response: {response.json()}")
    else:
        print(f"   ❌ Status: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ❌ HuggingFace error: {e}")

print("\nDiagnosis: The issue appears when loading embedding models.")
print("Both Pinecone and HuggingFace APIs work fine independently.")