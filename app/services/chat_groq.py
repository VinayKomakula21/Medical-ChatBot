"""
Chat service using Groq API for fast, high-quality responses
Groq provides extremely fast inference with generous free tier
"""
import logging
import time
import asyncio
import os
from functools import partial
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import UUID, uuid4
import requests
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import LLMException, VectorStoreException
from app.core.cache import cache
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse
from app.repositories.chat import chat_repository

logger = logging.getLogger(__name__)

# Medical chatbot prompt template - Optimized for RAG
SYSTEM_PROMPT = """You are MediBot, a knowledgeable medical assistant. Answer health questions using the provided medical information.

## HOW TO USE PROVIDED INFORMATION
When medical info is provided (marked [1], [2], etc.):
- **Prioritize this information** - it's from uploaded medical documents
- Cite sources naturally: "Symptoms include fever and fatigue [1]" or "According to [1], treatment involves..."
- Combine multiple sources when relevant: "Both rest [1] and hydration [2] are recommended"
- If info seems incomplete, supplement with general medical knowledge but note it

When NO medical info is provided:
- Use your general medical knowledge
- Be clear this is general advice, not from their documents

## RESPONSE STYLE
- **Direct answers** - Skip greetings, get to the point
- **Simple language** - "medicine" not "pharmaceutical", "shot" not "injection"
- **Structured format** - Use headers and bullets for clarity
- **Appropriate length** - Match response length to question complexity

## FORMAT GUIDE
```
**[Topic Header]**

- Bullet point 1
- Bullet point 2
- Bullet point 3

[Brief explanation if needed]

**When to see a doctor:**
- Warning sign 1
- Warning sign 2
```

## EMERGENCY HANDLING
For chest pain, difficulty breathing, severe bleeding, stroke symptoms:
🚨 Start with "**URGENT - Seek immediate medical help**"
Provide brief first-aid steps while waiting for help.

## CONVERSATION AWARENESS
- Remember context from earlier in the conversation
- If user asks follow-up ("what about side effects?"), connect to previous topic
- Ask clarifying questions if the query is too vague to answer safely

## KEY PRINCIPLES
1. Accuracy first - Don't guess about dosages or serious conditions
2. Cite sources when using provided medical info
3. Always include "see a doctor" guidance for anything beyond basic wellness
4. Be empathetic but efficient - people want answers, not fluff"""

class GroqChatService:
    """
    Uses Groq API for fast, high-quality LLM responses
    Free tier: 30 requests/minute, 14,400 requests/day
    """

    def __init__(self):
        # Groq API configuration
        from app.core.config import settings
        self.api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"  # Faster model for quick responses - Alternative: "mixtral-8x7b-32768"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        self._last_request_time = 0
        self._min_request_interval = 0.1  # Minimal delay for fast responses

        # Simple response cache for common queries
        self._response_cache = {}

    def _wait_for_rate_limit(self):
        """Rate limiting for free tier (30 requests per minute)"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _generate_with_groq(
        self,
        prompt: str,
        context: str,
        conversation_history: str = "",
        temperature: float = 0.5,
        max_tokens: int = 200
    ) -> str:
        """Generate response using Groq API with retry logic"""
        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()

                # Analyze urgency of the question
                urgent_keywords = ['chest pain', 'can\'t breathe', 'bleeding', 'emergency', 'severe pain', 'heart attack', 'stroke', 'choking']
                is_urgent = any(keyword in prompt.lower() for keyword in urgent_keywords)

                # Build user content with context
                user_content_parts = []

                # Add conversation history for follow-ups
                if conversation_history and conversation_history.strip():
                    user_content_parts.append(f"**Previous conversation:**\n{conversation_history}\n")

                # Add retrieved medical documents
                if context and context.strip():
                    user_content_parts.append(f"**Retrieved medical information:**\n{context[:800]}\n")

                # Add the current question
                if is_urgent:
                    user_content_parts.append(f"🚨 **URGENT QUESTION:** {prompt}")
                else:
                    user_content_parts.append(f"**Question:** {prompt}")

                user_content = "\n".join(user_content_parts)

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ]

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": 0.9,
                    "stream": False
                }

                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=10  # Reduced to 10 seconds for faster model
                )

                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]

                elif response.status_code == 429:
                    # Rate limit exceeded - retry
                    logger.warning(f"Groq rate limit exceeded, attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return "⏱️ API rate limit reached. Please wait a moment and try again."

                else:
                    logger.error(f"Groq API error: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return self._fallback_response(prompt, context)

            except requests.exceptions.Timeout:
                logger.error(f"Groq API request timed out, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "⏱️ **Request Timeout**\n\nThe AI service took too long to respond.\n\n**Quick tips:**\n\n- Try a shorter question\n- Ask about one topic at a time\n- Wait a moment and retry\n\n💡 For urgent medical help, call your doctor or 911."

            except Exception as e:
                logger.error(f"Error with Groq API: {e}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return self._fallback_response(prompt, context)

        # Should not reach here
        return self._fallback_response(prompt, context)

    def _fallback_response(self, prompt: str, context: str) -> str:
        """Fallback response when Groq API fails"""
        if context:
            return f"**Based on Available Medical Information:**\n\n{context[:800]}\n\n---\n\n⚠️ **Note:** The AI service is currently unavailable. The information above is from our medical knowledge base.\n\n💡 **Recommendation:** Please consult a healthcare professional for personalized medical advice."
        else:
            return "⚠️ **AI Service Temporarily Unavailable**\n\nI apologize for the inconvenience. The AI assistant is currently experiencing issues.\n\n**What you can do:**\n\n- Try asking your question again in a moment\n- Upload medical documents for context\n- Consult a healthcare professional for urgent medical advice\n\nThank you for your patience! 🏥"

    async def generate_response(
        self,
        request: ChatRequest,
        db: AsyncSession
    ) -> ChatResponse:
        start_time = time.time()
        conversation_id = request.conversation_id or uuid4()

        try:
            logger.info(f"Processing chat request with Groq: {request.message[:100]}...")

            # Check cache for simple queries (non-conversation)
            cache_key = None
            if not request.conversation_id:
                cache_key = f"chat:{request.message.lower().strip()}"
                cached_response = cache.get(cache_key)
                if cached_response:
                    logger.info("Returning cached response")
                    return ChatResponse(
                        response=cached_response["message"],
                        conversation_id=conversation_id,
                        sources=cached_response.get("sources", []),
                        processing_time=time.time() - start_time
                    )

            # Store user message in conversation history (now with db session)
            await chat_repository.add_message(
                db=db,
                conversation_id=conversation_id,
                role="user",
                content=request.message
            )

            # Get conversation context if this is a continuing conversation
            conversation_context = ""
            if request.conversation_id:
                conversation_context = await chat_repository.get_conversation_context(
                    db=db,
                    conversation_id=conversation_id,
                    max_messages=6  # Last 3 exchanges
                )

            # Search for relevant documents - only for complex queries
            sources = []
            context = ""

            # Skip document search for very simple queries to improve speed
            simple_queries = ['hi', 'hello', 'hey', 'thanks', 'thank you', 'ok', 'okay']
            is_simple_query = request.message.lower().strip() in simple_queries or len(request.message.split()) <= 3

            if not is_simple_query:
                try:
                    from app.db.pinecone import search_similar_documents
                    from app.services.query_processor import query_processor

                    logger.info("Searching for relevant documents...")

                    # Check if query needs decomposition
                    sub_queries = [request.message]
                    if query_processor.is_complex_query(request.message):
                        sub_queries = query_processor.decompose_query(request.message)
                        logger.info(f"Decomposed into {len(sub_queries)} sub-queries")

                    # Search for each sub-query and merge results
                    all_results = []
                    seen_ids = set()

                    for sub_query in sub_queries:
                        search_results = search_similar_documents(
                            query=sub_query,
                            k=5
                        )
                        for result in search_results:
                            result_id = result.get('id', result.get('content', '')[:50])
                            if result_id not in seen_ids:
                                all_results.append(result)
                                seen_ids.add(result_id)

                    # Take top 5 results
                    all_results = all_results[:5]

                    if all_results:
                        # Build sources with citation markers
                        sources = []
                        context_parts = []

                        for i, result in enumerate(all_results[:5]):
                            ref = f"[{i+1}]"
                            sources.append({
                                "ref": ref,
                                "content": result["content"][:200],
                                "metadata": result.get("metadata", {}),
                                "score": result.get("score", 0.0),
                                "filename": result.get("metadata", {}).get("filename", "Unknown")
                            })
                            context_parts.append(f"{ref} {result['content'][:400]}")

                        context = "\n\n".join(context_parts[:3])  # Use top 3 for context
                        logger.info(f"Found {len(sources)} relevant documents")

                except Exception as e:
                    logger.warning(f"Could not search documents: {e}")
                    context = ""
            else:
                logger.info("Skipping document search for simple query")

            # Generate response using Groq
            if not self.api_key:
                logger.warning("Groq API key not configured, using fallback")
                response_text = self._fallback_response(request.message, context)
            else:
                # Use temperature and max_tokens from request or defaults
                temperature = request.temperature or 0.7
                max_tokens = request.max_tokens or 500

                logger.info("Generating response with Groq...")

                # Run sync function in async context with conversation history
                generate_fn = partial(
                    self._generate_with_groq,
                    prompt=request.message,
                    context=context,
                    conversation_history=conversation_context,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                response_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    generate_fn
                )

                logger.info("Response generated successfully")

            # Store assistant's response in conversation history (now with db session)
            await chat_repository.add_message(
                db=db,
                conversation_id=conversation_id,
                role="assistant",
                content=response_text
            )

            # Add brief disclaimer if not already present
            if "consult" not in response_text.lower() and "healthcare professional" not in response_text.lower():
                response_text += "\n\n💡 **Note:** For personalized medical advice, please consult a healthcare professional."

            processing_time = time.time() - start_time

            # Cache response for simple queries (non-conversation)
            if cache_key:
                cache.set(cache_key, {
                    "message": response_text,
                    "sources": sources
                }, ttl=600)  # Cache for 10 minutes

            return ChatResponse(
                response=response_text,
                conversation_id=conversation_id,
                sources=sources,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return ChatResponse(
                response="I apologize, but I encountered an error. Please try rephrasing your question.",
                conversation_id=conversation_id,
                sources=[],
                processing_time=time.time() - start_time
            )

    async def generate_streaming_response(
        self,
        request: ChatRequest,
        db: AsyncSession
    ) -> AsyncGenerator[StreamingChatResponse, None]:
        """Generate streaming response (simulated for now)"""
        conversation_id = request.conversation_id or uuid4()

        try:
            # Generate full response first
            response = await self.generate_response(request, db)

            # Simulate streaming
            chunk_size = 50  # Larger chunks for Groq responses
            full_text = response.response

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                is_final = (i + chunk_size) >= len(full_text)

                yield StreamingChatResponse(
                    chunk=chunk,
                    conversation_id=conversation_id,
                    is_final=is_final,
                    sources=response.sources if is_final else None
                )

                await asyncio.sleep(0.01)  # Faster streaming

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield StreamingChatResponse(
                chunk="Error generating response.",
                conversation_id=conversation_id,
                is_final=True,
                sources=[]
            )

    async def get_conversation_history(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get conversation history from repository."""
        messages = await chat_repository.get_messages(db, conversation_id)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else ""
            }
            for msg in messages
        ]

    async def clear_conversation(
        self,
        db: AsyncSession,
        conversation_id: UUID
    ) -> bool:
        """Clear conversation history."""
        return await chat_repository.clear_messages(db, conversation_id)


# Singleton instance
groq_chat_service = GroqChatService()
