#!/usr/bin/env python3
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 50)
print("Testing Individual Components")
print("=" * 50)

# Test 1: Pinecone Connection
print("\n1. Testing Pinecone Connection...")
try:
    from pinecone import Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    indexes = pc.list_indexes().names()
    print(f"   ✅ Pinecone connected! Indexes: {indexes}")
except Exception as e:
    print(f"   ❌ Pinecone error: {e}")

# Test 2: Embeddings Model (without threading)
print("\n2. Testing Embeddings Model...")
try:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "1"

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    test_embedding = model.encode("test sentence")
    print(f"   ✅ Embeddings work! Shape: {test_embedding.shape}")
except Exception as e:
    print(f"   ❌ Embeddings error: {e}")

# Test 3: HuggingFace API (Direct)
print("\n3. Testing HuggingFace API...")
try:
    import requests

    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
    headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}

    response = requests.post(API_URL, headers=headers, json={
        "inputs": "What is diabetes?",
        "parameters": {"max_new_tokens": 50, "temperature": 0.5}
    }, timeout=10)

    if response.status_code == 200:
        print(f"   ✅ HuggingFace API works!")
        print(f"   Response preview: {str(response.json())[:100]}...")
    else:
        print(f"   ❌ HuggingFace API error: Status {response.status_code}")
        print(f"   Response: {response.text}")
except requests.Timeout:
    print(f"   ❌ HuggingFace API timeout after 10 seconds")
except Exception as e:
    print(f"   ❌ HuggingFace API error: {e}")

# Test 4: LangChain HuggingFace Integration
print("\n4. Testing LangChain HuggingFace Integration...")
try:
    from langchain_huggingface import HuggingFaceEndpoint

    llm = HuggingFaceEndpoint(
        repo_id="mistralai/Mistral-7B-Instruct-v0.3",
        temperature=0.5,
        max_new_tokens=50,
        huggingfacehub_api_token=os.getenv("HF_TOKEN"),
        timeout=10
    )

    start = time.time()
    response = llm.invoke("What is diabetes? Answer in one sentence.")
    elapsed = time.time() - start

    print(f"   ✅ LangChain HF works! Time: {elapsed:.2f}s")
    print(f"   Response: {response[:100]}...")
except Exception as e:
    print(f"   ❌ LangChain HF error: {e}")

# Test 5: Pinecone Vector Store (without adding documents)
print("\n5. Testing Pinecone Vector Store Query...")
try:
    from langchain_pinecone import PineconeVectorStore
    from langchain_huggingface import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True, 'batch_size': 1}
    )

    vector_store = PineconeVectorStore(
        index_name="medicbot",
        embedding=embeddings
    )

    # Just test initialization, not actual search
    print(f"   ✅ Vector store initialized successfully!")
except Exception as e:
    print(f"   ❌ Vector store error: {e}")

print("\n" + "=" * 50)
print("Diagnosis Complete!")
print("=" * 50)