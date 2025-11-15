# OAuth Authentication Setup Guide

This guide explains how to set up Google OAuth authentication for the Medical ChatBot application.

## 📋 Overview

The application now supports user authentication via Google OAuth 2.0. Users can:
- Login with their Google account
- Access protected endpoints (chat, documents)
- Manage their own conversations and uploaded documents
- Logout securely

## 🔐 Authentication Flow

```
1. User clicks "Login with Google" → GET /api/v1/auth/google/login
   ↓
2. Redirects to Google's OAuth consent screen
   ↓
3. User approves → Google redirects to /api/v1/auth/google/callback?code=...
   ↓
4. Backend exchanges code for Google access token
   ↓
5. Backend fetches user info from Google (email, name, avatar)
   ↓
6. Backend creates/updates user in database
   ↓
7. Backend generates JWT access token
   ↓
8. Redirects to frontend with JWT: http://localhost:3000/auth/callback?token=eyJ...
   ↓
9. Frontend stores JWT in localStorage/cookie
   ↓
10. Frontend sends JWT with every request: Authorization: Bearer eyJ...
```

## 🛠️ Setup Instructions

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

New packages added:
- `sqlalchemy` - Database ORM
- `aiosqlite` - Async SQLite driver
- `authlib` - OAuth client
- `python-jose[cryptography]` - JWT tokens
- `passlib[bcrypt]` - Password hashing

### Step 2: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Google+ API** or **Google Identity Services**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Configure consent screen:
   - User Type: External
   - App name: Medical ChatBot
   - User support email: your-email@gmail.com
   - Developer contact: your-email@gmail.com
6. Create OAuth Client ID:
   - Application type: **Web application**
   - Name: Medical ChatBot
   - Authorized redirect URIs:
     ```
     http://localhost:8000/api/v1/auth/google/callback
     http://127.0.0.1:8000/api/v1/auth/google/callback
     ```
7. Copy the **Client ID** and **Client Secret**

### Step 3: Configure Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Update the following variables in `.env`:

```bash
# Database (SQLite by default)
DATABASE_URL=sqlite+aiosqlite:///./medical_chatbot.db

# Generate a secure secret key
# Run: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=YOUR_GENERATED_SECRET_KEY_HERE

# JWT settings
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# Google OAuth credentials (from Step 2)
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

**Generate Secret Key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: Run the Application

```bash
python run_dev.py
```

The database will be automatically created on first startup.

### Step 5: Test Authentication

1. **Start the backend**: `python run_dev.py`
2. **Open Swagger docs**: http://localhost:8000/api/v1/docs
3. **Test login flow**:
   - Navigate to http://localhost:8000/api/v1/auth/google/login
   - Login with Google
   - You'll be redirected to frontend with token

## 🔒 Protected Endpoints

Once authenticated, users can access protected endpoints by including the JWT token:

```bash
# Get current user info
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/api/v1/auth/me

# Send chat message (requires authentication)
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"message": "What are flu symptoms?"}' \
     http://localhost:8000/api/v1/chat/message

# Upload document (requires authentication)
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -F "file=@document.pdf" \
     http://localhost:8000/api/v1/documents/upload
```

## 📊 Database Schema

The application creates the following tables:

### `users`
- `id` (String, Primary Key, UUID)
- `email` (String, Unique)
- `name` (String, Nullable)
- `avatar_url` (String, Nullable)
- `google_id` (String, Unique, for OAuth)
- `is_active` (Boolean)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### `conversations`
- `id` (String, Primary Key, UUID)
- `user_id` (String, Foreign Key → users.id)
- `title` (String, Nullable)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### `messages`
- `id` (String, Primary Key, UUID)
- `conversation_id` (String, Foreign Key → conversations.id)
- `role` (String: "user" or "assistant")
- `content` (Text)
- `created_at` (DateTime)

### `documents`
- `id` (String, Primary Key, UUID)
- `user_id` (String, Foreign Key → users.id)
- `filename` (String)
- `file_path` (String)
- `file_type` (String)
- `file_size` (Integer)
- `chunks_count` (Integer)
- `page_count` (Integer, Nullable)
- `pinecone_ids` (Text, JSON array)
- `tags` (Text, JSON array)
- `custom_metadata` (Text, JSON)
- `processing_time` (Float)
- `created_at` (DateTime)
- `updated_at` (DateTime)

## 🌐 API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/auth/google/login` | Initiate Google OAuth | No |
| GET | `/api/v1/auth/google/callback` | OAuth callback (internal) | No |
| GET | `/api/v1/auth/me` | Get current user info | Yes |
| POST | `/api/v1/auth/logout` | Logout (client deletes token) | Yes |

### Chat Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/chat/message` | Send chat message | Yes (future) |
| GET | `/api/v1/chat/history/{conv_id}` | Get conversation history | Yes (future) |
| DELETE | `/api/v1/chat/history/{conv_id}` | Delete conversation | Yes (future) |

### Document Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/documents/upload` | Upload document | Yes (future) |
| GET | `/api/v1/documents/` | List user's documents | Yes (future) |
| DELETE | `/api/v1/documents/{doc_id}` | Delete document | Yes (future) |

## 🧪 Testing

### Test with cURL

```bash
# 1. Login (open in browser)
open http://localhost:8000/api/v1/auth/google/login

# 2. After login, copy the JWT token from URL

# 3. Get user info
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/auth/me

# 4. Test protected endpoint
curl -X POST \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello"}' \
     http://localhost:8000/api/v1/chat/message
```

### Test with Swagger UI

1. Open http://localhost:8000/api/v1/docs
2. Click **Authorize** button (top right)
3. Enter: `Bearer YOUR_JWT_TOKEN`
4. Now you can test protected endpoints

## 🔧 Frontend Integration

### Example React/Next.js Integration

```javascript
// 1. Login Button Component
const LoginButton = () => {
  const handleLogin = () => {
    window.location.href = 'http://localhost:8000/api/v1/auth/google/login';
  };

  return <button onClick={handleLogin}>Login with Google</button>;
};

// 2. OAuth Callback Page (/auth/callback)
import { useEffect } from 'react';
import { useRouter } from 'next/router';

const AuthCallback = () => {
  const router = useRouter();

  useEffect(() => {
    const { token } = router.query;
    if (token) {
      // Store token
      localStorage.setItem('access_token', token);

      // Redirect to home
      router.push('/');
    }
  }, [router.query]);

  return <div>Logging you in...</div>;
};

// 3. API Client with Auth
const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1'
});

// Add token to all requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 4. Use in components
const sendMessage = async (message) => {
  const response = await api.post('/chat/message', { message });
  return response.data;
};
```

## 🚀 Production Deployment

### Environment Variables for Production

```bash
# Use PostgreSQL in production
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/medical_chatbot

# Generate a strong secret key (64+ characters)
SECRET_KEY=<generate-strong-key-here>

# Update OAuth redirect URI
GOOGLE_REDIRECT_URI=https://yourdomain.com/api/v1/auth/google/callback

# Update frontend URL
FRONTEND_URL=https://yourdomain.com

# Update CORS origins
BACKEND_CORS_ORIGINS=https://yourdomain.com

# Disable debug mode
DEBUG=false

# Increase workers
WORKERS=4
```

### Google OAuth Production Settings

1. Add production redirect URI in Google Console:
   ```
   https://yourdomain.com/api/v1/auth/google/callback
   ```

2. Update authorized JavaScript origins:
   ```
   https://yourdomain.com
   ```

## 🔍 Troubleshooting

### Issue: "Google OAuth is not configured"

**Solution:** Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in `.env`

### Issue: "redirect_uri_mismatch"

**Solution:** Make sure the redirect URI in your code matches exactly what's in Google Console:
```
http://localhost:8000/api/v1/auth/google/callback
```

### Issue: "Invalid authentication credentials"

**Solution:**
- Check if JWT token is expired (24 hours by default)
- Verify token is being sent in header: `Authorization: Bearer <token>`
- Check if `SECRET_KEY` matches between token creation and validation

### Issue: Database errors

**Solution:**
- Delete `medical_chatbot.db` and restart (will recreate tables)
- Check `DATABASE_URL` in `.env`

## 📚 Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT.io](https://jwt.io/) - Decode and inspect JWT tokens
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

## 💡 Next Steps

Current implementation provides:
- ✅ Google OAuth login
- ✅ JWT authentication
- ✅ User management
- ✅ Database setup

To complete the integration:
1. **Protect chat endpoints** - Add `current_user: User = Depends(get_current_user)` to chat endpoints
2. **Protect document endpoints** - Add authentication to upload/delete endpoints
3. **Migrate repositories** - Update chat/document repositories to use SQLAlchemy
4. **Frontend integration** - Build login UI and handle OAuth flow
5. **Add refresh tokens** - Implement token refresh mechanism (optional)
6. **Session management** - Track active sessions (optional)

---

**Need help?** Check the implementation in:
- `app/api/v1/endpoints/auth.py` - OAuth endpoints
- `app/services/auth.py` - JWT token service
- `app/core/security.py` - Authentication dependencies
- `app/db/models.py` - Database models
