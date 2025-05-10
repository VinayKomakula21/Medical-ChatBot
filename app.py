from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings, load_pdf, text_split
from langchain.vectorstores import Pinecone
import pinecone
from langchain.prompts import PromptTemplate
from langchain.llms import CTransformers
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
from src.prompt import prompt_template
import os
from langchain.llms import HuggingFaceHub
from langchain_pinecone import PineconeVectorStore
import shutil
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Get API keys from environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is not set")

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise ValueError("HF_TOKEN environment variable is not set")

embeddings = download_hugging_face_embeddings()

index_name = "medicbot"

#Loading the index
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)

PROMPT=PromptTemplate(template=prompt_template, input_variables=["context", "question"])

chain_type_kwargs={"prompt": PROMPT}

llm = HuggingFaceHub(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    model_kwargs={"temperature": 0.5, "max_length": 512},
    huggingfacehub_api_token=HF_TOKEN
)

qa=RetrievalQA.from_chain_type(
    llm=llm, 
    chain_type="stuff", 
    retriever=docsearch.as_retriever(search_kwargs={'k': 2}),
    return_source_documents=True, 
    chain_type_kwargs=chain_type_kwargs)

@app.route("/")
def index():
    return render_template('chat.html')

@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    input = msg
    print(input)
    result=qa({"query": input})
    # Extract only the helpful answer part
    response = result["result"].strip().split("Helpful answer:")[-1].strip()
    return response

@app.route("/upload", methods=["POST"])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith('.pdf'):
        return jsonify({"error": "Only PDF files are allowed"}), 400
    
    try:
        # Generate a unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save the uploaded file
        file.save(file_path)
        
        # Process the PDF
        documents = load_pdf(UPLOAD_FOLDER)
        text_chunks = text_split(documents)
        
        # Update the vector store with new documents
        global docsearch
        docsearch = PineconeVectorStore.from_texts(
            texts=[chunk.page_content for chunk in text_chunks],
            embedding=embeddings,
            index_name=index_name
        )
        
        # Update the QA chain with new retriever
        global qa
        qa = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=docsearch.as_retriever(search_kwargs={'k': 2}),
            return_source_documents=True,
            chain_type_kwargs=chain_type_kwargs
        )
        
        return jsonify({
            "message": "PDF processed successfully",
            "filename": filename
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port= 8080, debug= True)


