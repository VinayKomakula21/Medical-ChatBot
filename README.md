# MediBot - AI-Powered Medical Assistant

A modern, full-stack medical chatbot powered by RAG (Retrieval-Augmented Generation) architecture. Features real-time AI chat, document analysis, Google OAuth authentication, and a beautiful responsive UI.

![MediBot](https://img.shields.io/badge/MediBot-AI%20Medical%20Assistant-7C3AED)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688)
![React](https://img.shields.io/badge/React-19-61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6)
![Python](https://img.shields.io/badge/Python-3.11-3776AB)

## Features

- **AI-Powered Chat** - Intelligent responses using Groq LLM API with medical context
- **Document Analysis** - Upload PDF, DOCX, TXT files for knowledge base enhancement
- **Hybrid Search** - Combines semantic (vector) and keyword (BM25) search for accurate retrieval
- **Google OAuth** - Secure authentication with JWT tokens
- **Modern UI** - Responsive React frontend with dark mode support
- **Real-time Updates** - Streaming responses and WebSocket support

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI, Python 3.11, SQLAlchemy, Pydantic |
| **AI/ML** | Groq API, HuggingFace Embeddings, LangChain |
| **Database** | SQLite/PostgreSQL, Pinecone Vector DB |
| **Auth** | Google OAuth 2.0, JWT |
| **Deployment** | Render (Static Site + Web Service) |

## Architecture

```
├── app/                    # FastAPI Backend
│   ├── api/v1/            # API endpoints (auth, chat, documents)
│   ├── core/              # Config, security, logging
│   ├── services/          # Business logic (chat, embeddings, search)
│   ├── repositories/      # Data access layer
│   └── db/                # Database models and connections
│
├── frontend/              # React Frontend
│   ├── src/
│   │   ├── components/    # UI components (chat, layout, ui)
│   │   ├── contexts/      # Auth context
│   │   ├── pages/         # Route pages
│   │   ├── services/      # API client
│   │   └── hooks/         # Custom hooks
│   └── public/            # Static assets
│
└── requirements.txt       # Python dependencies
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- API Keys: Pinecone, Groq, HuggingFace, Google OAuth

### Backend Setup

```bash
# Clone repository
git clone https://github.com/VinayKomakula21/Medical-ChatBot.git
cd Medical-ChatBot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PINECONE_API_KEY=your_key
export GROQ_API_KEY=your_key
export HF_TOKEN=your_token
export GOOGLE_CLIENT_ID=your_client_id
export GOOGLE_CLIENT_SECRET=your_secret
export SECRET_KEY=your_jwt_secret

# Run server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set environment variable
export VITE_API_URL=http://localhost:8000

# Run development server
npm run dev
```

### Access Application

- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/api/v1/docs
- **ReDoc:** http://localhost:8000/api/v1/redoc

## API Endpoints

### Authentication
```http
GET  /api/v1/auth/google/login     # Initiate Google OAuth
GET  /api/v1/auth/google/callback  # OAuth callback
GET  /api/v1/auth/me               # Get current user
POST /api/v1/auth/logout           # Logout
```

### Chat
```http
POST /api/v1/chat/message          # Send message
GET  /api/v1/chat/history          # Get conversations
GET  /api/v1/chat/history/{id}     # Get conversation messages
DELETE /api/v1/chat/history/{id}   # Delete conversation
```

### Documents
```http
POST /api/v1/documents/upload      # Upload document
GET  /api/v1/documents/            # List documents
GET  /api/v1/documents/{id}        # Get document details
DELETE /api/v1/documents/{id}      # Delete document
POST /api/v1/documents/search      # Search documents
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PINECONE_API_KEY` | Pinecone vector DB API key | Yes |
| `GROQ_API_KEY` | Groq LLM API key | Yes |
| `HF_TOKEN` | HuggingFace API token | Yes |
| `SECRET_KEY` | JWT signing secret | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Yes |
| `DATABASE_URL` | Database connection string | No (defaults to SQLite) |
| `BACKEND_CORS_ORIGINS` | Allowed CORS origins | No |
| `FRONTEND_URL` | Frontend URL for OAuth redirect | No |

## Deployment

### Render Deployment

**Backend (Web Service):**
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**Frontend (Static Site):**
- Root Directory: `frontend`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`
- Add redirect rule: `/* → /index.html` (Rewrite)

## Screenshots

### Chat Interface
- Modern chat UI with AI responses
- Source citations from uploaded documents
- Conversation history in sidebar

### Document Management
- Drag-and-drop file upload
- Document list with metadata
- Search across all documents

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is for educational purposes. See [LICENSE](LICENSE) for details.

## Disclaimer

This chatbot is for educational and informational purposes only. Always consult qualified medical professionals for medical advice, diagnosis, or treatment.

---

**Built with** FastAPI, React, and Groq AI

**Author:** Vinay Komakula - [@VinayKomakula21](https://github.com/VinayKomakula21)
