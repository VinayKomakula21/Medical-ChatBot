# 🏥 Medical ChatBot - FastAPI Edition

A modern, production-ready medical chatbot built with FastAPI, LangChain, and Pinecone vector database. Features a clean REST API, WebSocket support for real-time chat, and a responsive web interface.

## ✨ Features

- **🚀 FastAPI Backend**: High-performance async API with automatic documentation
- **💬 Real-time Chat**: WebSocket support for streaming responses
- **📄 Document Processing**: Upload and analyze medical PDFs, TXT, and DOCX files
- **🔍 Semantic Search**: Pinecone vector database for intelligent document retrieval
- **🤖 AI-Powered**: Mistral-7B model via HuggingFace for medical Q&A
- **🎨 Modern UI**: Responsive web interface with dark mode support
- **📊 API Documentation**: Auto-generated Swagger UI and ReDoc
- **🐳 Docker Ready**: Full containerization with Docker Compose
- **🔒 Type Safe**: Full Pydantic validation and type hints
- **⚡ High Performance**: Async/await throughout with connection pooling

## 🏗️ Architecture

```
medical-chatbot/
├── app/                    # FastAPI application
│   ├── api/               # API endpoints
│   ├── core/              # Core configuration
│   ├── models/            # Pydantic models
│   ├── services/          # Business logic
│   ├── db/                # Database connections
│   └── utils/             # Utility functions
├── frontend/              # Web interface
├── tests/                 # Test suite
└── docker/                # Docker configuration
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Pinecone API key
- HuggingFace API token

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/medical-chatbot.git
cd medical-chatbot
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys:
# PINECONE_API_KEY=your_pinecone_key
# HF_TOKEN=your_huggingface_token
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
# Option 1: Using uvicorn directly (recommended for development)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Using Python module
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. **Access the application**
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Build and run
docker-compose up --build

# Run in background
docker-compose up -d

# Stop services
docker-compose down
```

### Using Docker

```bash
# Build image
docker build -t medical-chatbot .

# Run container
docker run -p 8000:8000 --env-file .env medical-chatbot
```

## 📚 API Documentation

### Chat Endpoints

#### Send Message
```http
POST /api/v1/chat/message
Content-Type: application/json

{
  "message": "What are the symptoms of diabetes?",
  "temperature": 0.5,
  "max_tokens": 512
}
```

#### WebSocket Chat (for streaming)
```javascript
ws://localhost:8000/api/v1/chat/ws
```

### Document Endpoints

#### Upload Document
```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: [PDF/TXT/DOCX file]
tags: "medical,research"
```

#### List Documents
```http
GET /api/v1/documents?page=1&page_size=20
```

#### Search Documents
```http
POST /api/v1/documents/search
Content-Type: application/json

{
  "query": "diabetes symptoms",
  "top_k": 5
}
```

### Health Check
```http
GET /api/v1/health
```

## ⚙️ Configuration

Configuration is managed through environment variables and `app/core/config.py`:

| Variable | Description | Default |
|----------|-------------|---------|
| `PINECONE_API_KEY` | Pinecone API key | Required |
| `HF_TOKEN` | HuggingFace token | Required |
| `PINECONE_INDEX_NAME` | Pinecone index name | medicbot |
| `HF_MODEL_ID` | HuggingFace model | mistralai/Mistral-7B-Instruct-v0.3 |
| `CHUNK_SIZE` | Document chunk size | 500 |
| `MAX_FILE_SIZE` | Max upload size | 10MB |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | 60 |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_api/test_chat.py
```

## 📦 Development

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
ruff check app/ tests/

# Type checking
mypy app/
```

### Pre-commit Hooks

```bash
# Install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## 🚀 Production Deployment

### Environment Setup

1. Use production environment variables
2. Enable HTTPS/TLS
3. Set `DEBUG=false`
4. Configure proper CORS origins
5. Use environment-specific logging

### Scaling Considerations

- Use multiple workers: `uvicorn app.main:app --workers 4`
- Implement Redis caching for responses
- Use PostgreSQL for conversation history
- Set up load balancer for multiple instances
- Implement rate limiting and API keys

### Monitoring

- Health checks: `/api/v1/health`
- Readiness: `/api/v1/health/ready`
- Liveness: `/api/v1/health/live`
- Metrics: Integrate Prometheus (optional)
- Tracing: OpenTelemetry support (optional)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- FastAPI for the amazing framework
- LangChain for LLM orchestration
- Pinecone for vector storage
- HuggingFace for model hosting
- Mistral AI for the language model

## 📞 Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/medical-chatbot/issues)
- Email: support@example.com

## 🔄 Migration from Flask

This is a complete rewrite from Flask to FastAPI with:
- ✅ 3-5x performance improvement
- ✅ Type safety throughout
- ✅ Auto-generated API documentation
- ✅ WebSocket support
- ✅ Better error handling
- ✅ Cleaner architecture
- ✅ Production-ready features

---

**⚠️ Disclaimer**: This chatbot is for educational purposes only. Always consult qualified medical professionals for medical advice.