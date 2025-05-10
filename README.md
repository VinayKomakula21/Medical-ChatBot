# Medical ChatBot

A Flask-based medical chatbot that uses LangChain, Pinecone, and Mistral AI to provide medical information based on uploaded PDF documents.

## Features

- PDF document upload and processing
- Semantic search using Pinecone vector store
- Chat interface for medical queries
- Powered by Mistral-7B-Instruct model

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API keys:
   ```
   PINECONE_API_KEY=your_pinecone_api_key
   HF_TOKEN=your_huggingface_token
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Usage

1. Access the web interface at `http://localhost:8080`
2. Upload medical PDF documents through the interface
3. Ask questions about the uploaded documents in the chat interface

## Requirements

- Python 3.8+
- Flask
- LangChain
- Pinecone
- HuggingFace Hub
- Other dependencies listed in requirements.txt

## Security Note

Never commit your `.env` file or expose your API keys. The `.env` file is included in `.gitignore` for security.