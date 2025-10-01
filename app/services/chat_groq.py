"""
Chat service using Groq API for fast, high-quality responses
Groq provides extremely fast inference with generous free tier
"""
import logging
import time
import asyncio
import os
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import UUID, uuid4
import requests
import json

from app.core.config import settings
from app.core.exceptions import LLMException, VectorStoreException
from app.core.cache import cache
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse
from app.repositories.chat import chat_repository
from app.repositories.document import document_repository

logger = logging.getLogger(__name__)

# Medical chatbot prompt template
SYSTEM_PROMPT = """You are MediBot, a friendly medical assistant. Give simple, easy-to-understand health advice.

🎯 CORE RULES:

1. **KEEP IT SHORT & SIMPLE**
   - Short questions = Short answers (3-5 bullet points)
   - Detailed questions = Detailed answers (but still clear)
   - Use everyday language, not medical jargon

2. **SKIP THE FLUFF**
   - No greetings ("I understand...", "I'm happy to help...")
   - No long introductions
   - Jump straight to the answer

3. **BE CONVERSATIONAL**
   - Write like you're talking to a friend
   - Use simple words (say "sick" not "ill", "shot" not "injection")
   - Keep sentences short and clear

📝 RESPONSE EXAMPLES:

**Example 1 - Simple Question:**
User: "Headache remedies"
Good Response:
**Quick Relief:**

- Drink 2 glasses of water
- Rest in a dark, quiet room
- Cold pack on forehead
- Take ibuprofen or acetaminophen
- Massage your temples gently

⚠️ See a doctor if pain is severe or lasts 3+ days.

**Example 1B - Fever:**
User: "fever remedies"
Good Response:
**Fever Relief:**

- Drink lots of fluids (water, clear broth)
- Take acetaminophen (Tylenol) or ibuprofen (Advil)
- Cool compress or cool bath
- Rest in a cool room
- Light clothing

**See a doctor if:**
- Fever over 104°F (40°C)
- Lasts more than 3 days
- Severe headache or confusion

**Example 2 - Symptom Question:**
User: "Symptoms of flu"
Good Response:
**Common Flu Symptoms:**

- High fever (100-104°F)
- Body aches and chills
- Dry cough
- Sore throat
- Extreme tiredness
- Headache
- Stuffy or runny nose

Most people feel better in 7-10 days. See a doctor if you have trouble breathing or chest pain.

**Example 3 - Emergency:**
User: "Chest pain and shortness of breath"
Good Response:
🚨 **THIS IS URGENT**

Call 911 immediately if you have:
- Chest pain or pressure
- Trouble breathing
- Pain spreading to arm, jaw, or back

While waiting:
- Sit down and stay calm
- Loosen tight clothing
- Don't drive yourself

This could be a heart attack - get help NOW.

**Example 4 - Explanation:**
User: "What is diabetes?"
Good Response:
**Diabetes Explained Simply:**

Diabetes means your blood sugar (glucose) is too high. Your body either:
- Doesn't make enough insulin (Type 1)
- Can't use insulin properly (Type 2)

Think of insulin as a key that lets sugar into your cells for energy. Without it, sugar builds up in your blood.

**Common Signs:**
- Very thirsty and peeing a lot
- Always tired
- Blurry vision
- Slow-healing cuts

**Good News:** It's manageable with medicine, diet, and exercise. Talk to your doctor if you have these symptoms.

🎨 FORMATTING RULES:

✅ DO:
- Use bullet points (-) - Keep each point SHORT (5-10 words max)
- Bold section headers (**Like This:**)
- Add line breaks before and after lists
- Use simple, everyday words
- Keep bullet points action-focused (start with verbs when possible)

❌ DON'T:
- Write long bullet points (no parentheses or extra explanations in bullets)
- Use medical jargon (say "medicine" not "pharmaceutical", "shot" not "injection")
- Write long paragraphs
- Add unnecessary details
- Mention "based on the context" or "documents"

🎯 RESPONSE LENGTH GUIDE:

| Question Type | Max Words | Example |
|--------------|-----------|---------|
| Simple remedy/tip | 80-120 | "Cold remedies" |
| Symptoms list | 100-150 | "Flu symptoms" |
| Explanation | 150-200 | "What is diabetes?" |
| Emergency | 60-100 | "Chest pain help" |

💡 REMEMBER:
- You're helping regular people, not doctors
- Simple = Better
- If mom/grandma can understand it, it's good
- Keep bullet points under 10 words each
- Always end with "See a doctor if..." section (use bold header)

CRITICAL: Shorter bullet points = easier to read = better user experience!

Be helpful, be clear, be brief. That's it!"""

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

    def _generate_with_groq(self, prompt: str, context: str, temperature: float = 0.5, max_tokens: int = 200) -> str:
        """Generate response using Groq API with retry logic"""
        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()

                # Format the messages for chat completion
                # Analyze urgency of the question
                urgent_keywords = ['chest pain', 'can\'t breathe', 'bleeding', 'emergency', 'severe pain', 'heart attack', 'stroke', 'choking']
                is_urgent = any(keyword in prompt.lower() for keyword in urgent_keywords)

                # Keep user content simple and direct
                if is_urgent:
                    user_content = f"🚨 URGENT: {prompt}\n\n(Provide emergency guidance immediately)"
                elif context and context.strip():
                    user_content = f"Question: {prompt}\n\nRelevant medical info:\n{context[:600]}"
                else:
                    user_content = prompt

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
        request: ChatRequest
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
                        message=cached_response["message"],
                        conversation_id=conversation_id,
                        sources=cached_response.get("sources", []),
                        processing_time=time.time() - start_time
                    )

            # Store user message in conversation history
            await chat_repository.add_message(
                conversation_id=conversation_id,
                role="user",
                content=request.message
            )

            # Get conversation context if this is a continuing conversation
            conversation_context = ""
            if request.conversation_id:
                conversation_context = await chat_repository.get_conversation_context(
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
                    logger.info("Searching for relevant documents...")

                    search_results = search_similar_documents(
                        query=request.message,
                        k=2  # Reduced from 3 to 2 for faster search
                    )

                    if search_results:
                        sources = [
                            {
                                "content": result["content"][:150],  # Reduced from 200
                                "metadata": result.get("metadata", {})
                            }
                            for result in search_results
                        ]
                        # Combine top results for context - reduced to top 2
                        context = "\n\n".join([result["content"][:400] for result in search_results[:2]])
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

                # Run sync function in async context
                response_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._generate_with_groq,
                    request.message,
                    context,
                    temperature,
                    max_tokens
                )

                logger.info("Response generated successfully")

            # Store assistant's response in conversation history
            await chat_repository.add_message(
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
        request: ChatRequest
    ) -> AsyncGenerator[StreamingChatResponse, None]:
        """Generate streaming response (simulated for now)"""
        conversation_id = request.conversation_id or uuid4()

        try:
            # Generate full response first
            response = await self.generate_response(request)

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

    async def get_conversation_history(self, conversation_id: UUID) -> List[Dict[str, Any]]:
        """Get conversation history from repository."""
        messages = await chat_repository.get_messages(conversation_id)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ]

    async def clear_conversation(self, conversation_id: UUID) -> bool:
        """Clear conversation history."""
        return await chat_repository.clear_messages(conversation_id)

# Singleton instance
groq_chat_service = GroqChatService()