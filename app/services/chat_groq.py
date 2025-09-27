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
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse
from app.repositories.chat import chat_repository
from app.repositories.document import document_repository

logger = logging.getLogger(__name__)

# Medical chatbot prompt template
SYSTEM_PROMPT = """You are MediBot, a caring and knowledgeable medical assistant. Your role is to help users understand health topics and provide helpful medical information.

🎯 YOUR PERSONALITY:
• Warm, empathetic, and supportive
• Professional yet approachable
• Patient and understanding
• Clear and easy to understand

📋 RESPONSE GUIDELINES:

For URGENT/EMERGENCY situations (fever, pain, bleeding, etc.):
1. Start with immediate relief steps
2. List warning signs to watch for
3. Clearly state when to seek medical help
4. Keep it concise and actionable

For GENERAL HEALTH QUESTIONS:
1. Provide comprehensive information
2. Explain in simple terms
3. Include prevention tips when relevant
4. Offer practical advice

For SYMPTOM INQUIRIES:
1. Acknowledge their concern
2. Explain possible causes
3. Suggest home remedies if appropriate
4. Advise when to see a doctor

⚡ ADAPT YOUR RESPONSE LENGTH:
• "I have fever!" → Quick relief steps (3-5 points)
• "What is diabetes?" → Detailed explanation
• "Headache for 3 days" → Causes + remedies + when to worry

🚫 NEVER DO:
• Don't mention "context", "documents", or data sources
• Don't discuss unrelated conditions
• Don't be overly technical
• Don't alarm unnecessarily

✅ ALWAYS DO:
• Address the user's specific concern
• Use **bold** for important points
• Use • bullets for lists
• Stay focused on their question
• Be genuinely helpful

💡 FORMATTING:
• Use clear sections with **headings**
• Keep paragraphs short (2-3 sentences)
• Use bullet points for steps
• Add emojis sparingly for friendliness (🌡️ for fever, 💊 for medicine, etc.)

Remember: You're speaking to someone seeking help. Be the friendly, knowledgeable health advisor they need."""

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
        self.model = "llama-3.3-70b-versatile"  # Latest Llama model - also available: "llama-3.2-90b-text-preview", "mixtral-8x7b-32768"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        self._last_request_time = 0
        self._min_request_interval = 0.5  # Reduced rate limiting for better response time

    def _wait_for_rate_limit(self):
        """Rate limiting for free tier (30 requests per minute)"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _generate_with_groq(self, prompt: str, context: str, temperature: float = 0.7, max_tokens: int = 500) -> str:
        """Generate response using Groq API"""
        try:
            self._wait_for_rate_limit()

            # Format the messages for chat completion
            # Analyze urgency of the question
            urgent_keywords = ['fever', 'pain', 'bleeding', 'emergency', 'help', 'hurts', 'urgent', '!!!', 'what to do']
            is_urgent = any(keyword in prompt.lower() for keyword in urgent_keywords)

            if context and context.strip():
                if is_urgent:
                    user_content = f"""Medical Reference: {context[:500]}

User's Concern: {prompt}

This seems urgent. Provide immediate, actionable advice. Be concise and helpful."""
                else:
                    user_content = f"""Medical Reference: {context}

User's Question: {prompt}

Provide a helpful, informative response."""
            else:
                if is_urgent:
                    user_content = f"""User's Concern: {prompt}

This seems urgent. Provide immediate, actionable advice. Focus on what they should do right now."""
                else:
                    user_content = f"""User's Question: {prompt}

Provide a helpful, informative response based on medical knowledge."""

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
                timeout=60  # Increased timeout for better reliability
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]

            elif response.status_code == 429:
                # Rate limit exceeded
                logger.warning("Groq rate limit exceeded, waiting...")
                time.sleep(5)
                return "Rate limit exceeded. Please try again in a moment."

            else:
                logger.error(f"Groq API error: {response.status_code} - {response.text}")
                return self._fallback_response(prompt, context)

        except requests.exceptions.Timeout:
            logger.error("Groq API request timed out")
            return "The request timed out. Please try again."

        except Exception as e:
            logger.error(f"Error with Groq API: {e}")
            return self._fallback_response(prompt, context)

    def _fallback_response(self, prompt: str, context: str) -> str:
        """Fallback response when Groq API fails"""
        if context:
            return f"Based on available information: {context[:500]}...\n\nNote: Full AI response unavailable. Please consult a healthcare professional for detailed medical advice."
        else:
            return "I apologize, but I'm unable to generate a detailed response at this moment. Please consult a healthcare professional for medical advice."

    async def generate_response(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        start_time = time.time()
        conversation_id = request.conversation_id or uuid4()

        try:
            logger.info(f"Processing chat request with Groq: {request.message[:100]}...")

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

            # Search for relevant documents
            sources = []
            context = ""

            try:
                from app.db.pinecone import search_similar_documents
                logger.info("Searching for relevant documents...")

                search_results = search_similar_documents(
                    query=request.message,
                    k=settings.retriever_k
                )

                if search_results:
                    sources = [
                        {
                            "content": result["content"][:200],
                            "metadata": result.get("metadata", {})
                        }
                        for result in search_results
                    ]
                    # Combine top results for context (use more for Groq)
                    context = "\n\n".join([result["content"] for result in search_results[:3]])
                    logger.info(f"Found {len(sources)} relevant documents")
                else:
                    logger.info("No relevant documents found")

            except Exception as e:
                logger.warning(f"Could not search documents: {e}")
                context = ""

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