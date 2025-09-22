import logging
import time
import asyncio
import requests
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import UUID, uuid4
from functools import lru_cache

from app.core.config import settings
from app.core.exceptions import LLMException, VectorStoreException
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse

logger = logging.getLogger(__name__)

# Medical chatbot prompt template
PROMPT_TEMPLATE = """You are a helpful medical information assistant. Use the following context to answer the question.
If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context: {context}

Question: {question}

Provide a clear, accurate, and helpful answer:"""

class ChatService:
    def __init__(self):
        # Use a model that's actually available on HF free tier
        # Options: gpt2, distilgpt2, google/flan-t5-base, facebook/bart-large-cnn
        self.model_id = "google/flan-t5-base"
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        self.headers = {"Authorization": f"Bearer {settings.HF_TOKEN}"}
        self._last_request_time = 0
        self._min_request_interval = 0.5  # Rate limiting for free tier

    def _wait_for_rate_limit(self):
        """Rate limiting for free tier"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    @lru_cache(maxsize=128)
    def _generate_cached(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Cached LLM generation via HF API"""
        try:
            self._wait_for_rate_limit()

            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "do_sample": True,
                    "top_p": 0.95,
                    "return_full_text": False
                }
            }

            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=15
            )

            if response.status_code == 503:
                # Model is loading
                logger.info("Model is loading, waiting 20 seconds...")
                time.sleep(20)
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=15
                )

            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get('generated_text', '')
                return str(result)
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return "I apologize, but I'm having trouble generating a response. Please try again."

        except requests.exceptions.Timeout:
            logger.error("API request timed out")
            return "The request timed out. Please try again with a simpler question."
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I encountered an error while processing your request."

    async def generate_response(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        start_time = time.time()
        conversation_id = request.conversation_id or uuid4()

        try:
            logger.info(f"Processing chat request: {request.message[:100]}...")

            # Search for relevant documents using the new API-based embeddings
            sources = []
            context = ""

            try:
                from app.db.pinecone import search_similar_documents
                logger.info(f"Searching for relevant documents...")

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
                    # Combine top results for context
                    context = "\n\n".join([result["content"] for result in search_results[:2]])
                    logger.info(f"Found {len(sources)} relevant documents")
                else:
                    logger.info("No relevant documents found")

            except Exception as e:
                logger.warning(f"Could not search documents: {e}")
                # Continue without context

            # Generate response using Phi-2 via HF API
            try:
                # Format the prompt
                formatted_prompt = PROMPT_TEMPLATE.format(
                    context=context if context else "No specific medical context available.",
                    question=request.message
                )

                # Use temperature and max_tokens from request or defaults
                temperature = request.temperature or settings.LLM_TEMPERATURE
                max_tokens = request.max_tokens or settings.LLM_MAX_LENGTH

                logger.info("Generating response with Phi-2...")

                # Use asyncio to run the sync function
                response_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._generate_cached,
                    formatted_prompt,
                    max_tokens,
                    temperature
                )

                logger.info(f"Generated response successfully")

            except Exception as llm_error:
                logger.error(f"LLM generation failed: {llm_error}")
                # Provide a helpful fallback response
                response_text = (
                    "I apologize, but I'm having trouble generating a response right now. "
                    "This could be due to high demand on the free tier. Please try again in a moment, "
                    "or try asking a simpler question."
                )

            processing_time = time.time() - start_time

            return ChatResponse(
                response=response_text,
                conversation_id=conversation_id,
                sources=sources,
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            # Return a basic error response instead of raising
            return ChatResponse(
                response="I'm sorry, I encountered an error processing your request. Please try again.",
                conversation_id=conversation_id,
                sources=[],
                processing_time=time.time() - start_time
            )

    async def generate_streaming_response(
        self,
        request: ChatRequest
    ) -> AsyncGenerator[StreamingChatResponse, None]:
        conversation_id = request.conversation_id or uuid4()

        try:
            # For streaming, we'll simulate it by chunking the response
            response = await self.generate_response(request)

            # Simulate streaming by chunking the response
            chunk_size = 20  # characters per chunk
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

                # Small delay to simulate streaming
                await asyncio.sleep(0.05)

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
        conversation_id: UUID
    ) -> List[Dict[str, Any]]:
        # This would typically fetch from a database
        # For now, returning empty list as we're not persisting conversations
        return []

    async def clear_conversation(
        self,
        conversation_id: UUID
    ) -> bool:
        # This would typically clear from a database
        # For now, just return success
        return True

# Singleton instance
chat_service = ChatService()