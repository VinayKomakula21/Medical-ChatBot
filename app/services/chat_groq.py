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
import httpx
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core import observability as obs
from app.core.exceptions import LLMException, VectorStoreException
from app.core.cache import cache
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse
from app.repositories.chat import chat_repository
from app.services.safety import safety_service

logger = logging.getLogger(__name__)

# Medical chatbot prompt template - Optimized for grounded RAG
SYSTEM_PROMPT = """You are MediBot, a careful medical assistant. Your single most important rule: **never invent medical facts that are not supported by the provided information**.

## HOW TO USE PROVIDED INFORMATION
When medical info is provided (marked [1], [2], etc.):
- **Answer ONLY from this information.** Treat it as the authoritative source for this question.
- Cite every factual claim with the matching marker: "Symptoms include fever and fatigue [1]" or "According to [1], treatment involves..."
- Combine multiple sources when they agree: "Both rest [1] and hydration [2] are recommended."
- **If the provided information does not answer the question** — even partially — say so plainly:
  > "I don't have reliable information on this in the sources you provided. Please consult a qualified medical professional."
  Then stop. Do not fill the gap with general knowledge — that is exactly the failure mode that makes medical AI unsafe.
- It is always better to admit a gap than to guess.

When NO medical info is provided (zero sources retrieved):
- You may use general medical knowledge, but **lead with a clear caveat**: "I don't have specific sources for this, but in general..."
- Keep it short. Defer to a clinician for anything specific (dosages, diagnoses, drug interactions).

## RESPONSE STYLE
- **Direct answers** - Skip greetings, get to the point
- **Simple language** - "medicine" not "pharmaceutical", "shot" not "injection"
- **Structured format** - Use headers and bullets for clarity
- **Appropriate length** - Match response length to question complexity. Short questions get short answers.

## FORMAT GUIDE
```
**[Topic Header]**

- Bullet point 1 [1]
- Bullet point 2 [2]
- Bullet point 3 [1]

[Brief explanation if needed]

**When to see a doctor:**
- Warning sign 1
- Warning sign 2
```

## EMERGENCY HANDLING
For chest pain, difficulty breathing, severe bleeding, stroke symptoms:
🚨 Start with "**URGENT - Seek immediate medical help (call 911 or your local emergency number).**"
Provide brief first-aid steps while waiting for help.

## CONVERSATION AWARENESS
- Remember context from earlier in the conversation
- If user asks follow-up ("what about side effects?"), connect to previous topic
- Ask a clarifying question if the query is too vague to answer safely

## KEY PRINCIPLES
1. **Grounded over confident** - Cite, or admit the gap. Never invent facts.
2. **No diagnosis, no prescription** - Describe and inform; refer specific medical decisions to a clinician.
3. **Always include "see a doctor" guidance** for anything beyond basic wellness.
4. **Be empathetic but efficient** - People want clear answers, not fluff."""

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

    async def _wait_for_rate_limit(self) -> None:
        """Rate limiting for free tier (30 requests per minute)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    async def _generate_with_groq(
        self,
        prompt: str,
        context: str,
        conversation_history: str = "",
        temperature: float = 0.5,
        max_tokens: int = 200,
        trace: Any = None,
    ) -> str:
        """Generate response using Groq API with retry logic (async, httpx).

        Args:
            trace: optional Langfuse trace/span to nest this generation under.
                   No-op when observability is disabled.
        """
        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                await self._wait_for_rate_limit()

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

                with obs.generation(
                    trace,
                    name="groq.chat_completion",
                    model=self.model,
                    input=messages,
                    model_parameters={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": 0.9,
                    },
                    metadata={"attempt": attempt + 1, "is_urgent": is_urgent},
                ) as gen:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(
                            self.api_url,
                            headers=self.headers,
                            json=payload,
                        )

                    if response.status_code == 200:
                        result = response.json()
                        text = result["choices"][0]["message"]["content"]
                        usage = result.get("usage") or {}
                        gen.update(
                            output=text,
                            usage={
                                "input": usage.get("prompt_tokens"),
                                "output": usage.get("completion_tokens"),
                                "total": usage.get("total_tokens"),
                            },
                        )
                        return text

                    if response.status_code == 429:
                        # Rate limit exceeded - retry
                        gen.update(metadata={"http_status": 429})
                        logger.warning(f"Groq rate limit exceeded, attempt {attempt + 1}/{max_retries}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            continue
                        return "⏱️ API rate limit reached. Please wait a moment and try again."

                    gen.update(metadata={"http_status": response.status_code})
                    logger.error(f"Groq API error: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return self._fallback_response(prompt, context)

            except httpx.TimeoutException:
                logger.error(f"Groq API request timed out, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return "⏱️ **Request Timeout**\n\nThe AI service took too long to respond.\n\n**Quick tips:**\n\n- Try a shorter question\n- Ask about one topic at a time\n- Wait a moment and retry\n\n💡 For urgent medical help, call your doctor or 911."

            except Exception as e:
                logger.error(f"Error with Groq API: {e}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
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
        trace_id_str: Optional[str] = None

        with obs.trace(
            name="chat.message",
            metadata={
                "conversation_id": str(conversation_id),
                "message_preview": request.message[:120],
            },
        ) as trace:
            trace_id_str = getattr(trace, "id", None)
            try:
                trace.update(input={"message": request.message})
            except Exception:  # noqa: BLE001
                pass

            try:
                logger.info(f"Processing chat request with Groq: {request.message[:100]}...")

                # Check cache for simple queries (non-conversation)
                cache_key = None
                if not request.conversation_id:
                    cache_key = f"chat:{request.message.lower().strip()}"
                    cached_response = cache.get(cache_key)
                    if cached_response:
                        logger.info("Returning cached response")
                        try:
                            trace.update(metadata={"cache_hit": True})
                        except Exception:  # noqa: BLE001
                            pass
                        return ChatResponse(
                            response=cached_response["message"],
                            conversation_id=conversation_id,
                            sources=cached_response.get("sources", []),
                            processing_time=time.time() - start_time,
                            trace_id=trace_id_str,
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
                    with obs.span(trace, name="retrieval", input={"query": request.message}) as ret_span:
                        try:
                            from app.services.hybrid_search import hybrid_search_service
                            from app.services.query_processor import query_processor

                            logger.info("Searching for relevant documents...")

                            # Check if query needs decomposition
                            sub_queries = [request.message]
                            if query_processor.is_complex_query(request.message):
                                sub_queries = query_processor.decompose_query(request.message)
                                logger.info(f"Decomposed into {len(sub_queries)} sub-queries")

                            # Hybrid retrieval (vector + BM25 + RRF, optional reranker) for each sub-query
                            all_results = []
                            seen_ids = set()

                            for sub_query in sub_queries:
                                search_results = hybrid_search_service.search(
                                    query=sub_query,
                                    top_k=5,
                                    trace=ret_span,
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

                            try:
                                ret_span.update(
                                    output={
                                        "n_sub_queries": len(sub_queries),
                                        "n_results": len(all_results),
                                        "top_score": all_results[0].get("score") if all_results else None,
                                    }
                                )
                            except Exception:  # noqa: BLE001
                                pass

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

                    # _generate_with_groq is async (httpx) — no executor needed.
                    # Trace propagates so the Groq generation span nests under it.
                    response_text = await self._generate_with_groq(
                        prompt=request.message,
                        context=context,
                        conversation_history=conversation_context,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        trace=trace,
                    )

                    logger.info("Response generated successfully")

                # SafetyService — out-of-scope banner, emergency routing,
                # faithfulness check, drug-name validation. Annotates the
                # response with banners; doesn't block.
                try:
                    # Build retrieved_chunks shape SafetyService expects.
                    chunks_for_safety = [
                        {"content": s.get("content", "")} for s in sources
                    ]
                    verdict = await safety_service.check(
                        question=request.message,
                        retrieved_chunks=chunks_for_safety,
                        answer=response_text,
                    )
                    response_text = verdict.annotated_answer
                    try:
                        trace.update(metadata={
                            "safety.out_of_scope": verdict.out_of_scope,
                            "safety.is_emergency": verdict.is_emergency,
                            "safety.faithfulness": verdict.faithfulness_score,
                            "safety.unverified_drugs": verdict.unverified_drugs,
                        })
                    except Exception:  # noqa: BLE001
                        pass
                except Exception as safety_exc:  # noqa: BLE001
                    # Safety check is best-effort — never block on its failure.
                    logger.warning("SafetyService failed: %s", safety_exc)

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

                try:
                    trace.update(output={"response": response_text[:500], "n_sources": len(sources)})
                except Exception:  # noqa: BLE001
                    pass

                return ChatResponse(
                    response=response_text,
                    conversation_id=conversation_id,
                    sources=sources,
                    processing_time=processing_time,
                    trace_id=trace_id_str,
                )

            except Exception as e:
                logger.error(f"Error generating response: {e}")
                return ChatResponse(
                    response="I apologize, but I encountered an error. Please try rephrasing your question.",
                    conversation_id=conversation_id,
                    sources=[],
                    processing_time=time.time() - start_time,
                    trace_id=trace_id_str,
                )

    async def generate_streaming_response(
        self,
        request: ChatRequest,
        db: AsyncSession
    ) -> AsyncGenerator[StreamingChatResponse, None]:
        """Stream tokens from Groq in real time via SSE.

        Previously this method called generate_response() (full response) and
        chunked it with asyncio.sleep — that's fake streaming. This version
        opens an httpx stream against Groq's OpenAI-compatible /chat/completions
        with `stream: true` and yields each token delta as it arrives.
        """
        import httpx  # local import keeps module load cheap when streaming unused

        conversation_id = request.conversation_id or uuid4()

        with obs.trace(
            name="chat.stream",
            metadata={
                "conversation_id": str(conversation_id),
                "message_preview": request.message[:120],
            },
        ) as trace:
            try:
                # 1. Persist user message
                await chat_repository.add_message(
                    db=db,
                    conversation_id=conversation_id,
                    role="user",
                    content=request.message,
                )

                # 2. Pull conversation history for follow-up coherence
                conversation_context = ""
                if request.conversation_id:
                    conversation_context = await chat_repository.get_conversation_context(
                        db=db,
                        conversation_id=conversation_id,
                        max_messages=6,
                    )

                # 3. Retrieve context (skip for trivial messages)
                simple_queries = ['hi', 'hello', 'hey', 'thanks', 'thank you', 'ok', 'okay']
                is_simple = (
                    request.message.lower().strip() in simple_queries
                    or len(request.message.split()) <= 3
                )

                sources: List[Dict[str, Any]] = []
                context = ""
                if not is_simple:
                    with obs.span(trace, name="retrieval", input={"query": request.message}) as ret_span:
                        try:
                            from app.services.hybrid_search import hybrid_search_service
                            from app.services.query_processor import query_processor

                            sub_queries = [request.message]
                            if query_processor.is_complex_query(request.message):
                                sub_queries = query_processor.decompose_query(request.message)

                            all_results = []
                            seen_ids = set()
                            for sq in sub_queries:
                                for r in hybrid_search_service.search(query=sq, top_k=5, trace=ret_span):
                                    rid = r.get('id', r.get('content', '')[:50])
                                    if rid not in seen_ids:
                                        all_results.append(r)
                                        seen_ids.add(rid)
                            all_results = all_results[:5]

                            if all_results:
                                ctx_parts = []
                                for i, r in enumerate(all_results):
                                    ref = f"[{i+1}]"
                                    sources.append({
                                        "ref": ref,
                                        "content": r["content"][:200],
                                        "metadata": r.get("metadata", {}),
                                        "score": r.get("score", 0.0),
                                        "filename": r.get("metadata", {}).get("filename", "Unknown"),
                                    })
                                    ctx_parts.append(f"{ref} {r['content'][:400]}")
                                context = "\n\n".join(ctx_parts[:3])

                            try:
                                ret_span.update(output={"n_results": len(all_results)})
                            except Exception:  # noqa: BLE001
                                pass
                        except Exception as e:
                            logger.warning(f"Streaming retrieval failed: {e}")

                # 4. Build messages identically to _generate_with_groq
                urgent_keywords = [
                    'chest pain', "can't breathe", 'bleeding', 'emergency',
                    'severe pain', 'heart attack', 'stroke', 'choking',
                ]
                is_urgent = any(k in request.message.lower() for k in urgent_keywords)

                user_content_parts = []
                if conversation_context and conversation_context.strip():
                    user_content_parts.append(f"**Previous conversation:**\n{conversation_context}\n")
                if context and context.strip():
                    user_content_parts.append(f"**Retrieved medical information:**\n{context[:800]}\n")
                if is_urgent:
                    user_content_parts.append(f"🚨 **URGENT QUESTION:** {request.message}")
                else:
                    user_content_parts.append(f"**Question:** {request.message}")

                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "\n".join(user_content_parts)},
                ]

                temperature = request.temperature or 0.7
                max_tokens = request.max_tokens or 500

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": 0.9,
                    "stream": True,
                }

                # 5. Stream from Groq SSE; emit each token delta as it arrives.
                full_text_parts: List[str] = []
                with obs.generation(
                    trace,
                    name="groq.chat_completion.stream",
                    model=self.model,
                    input=messages,
                    model_parameters={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": 0.9,
                        "stream": True,
                    },
                    metadata={"is_urgent": is_urgent},
                ) as gen:
                    if not self.api_key:
                        fb = self._fallback_response(request.message, context)
                        full_text_parts.append(fb)
                        yield StreamingChatResponse(
                            chunk=fb, conversation_id=conversation_id, is_final=False,
                        )
                    else:
                        try:
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                async with client.stream(
                                    "POST",
                                    self.api_url,
                                    headers=self.headers,
                                    json=payload,
                                ) as resp:
                                    if resp.status_code != 200:
                                        err = await resp.aread()
                                        logger.error(
                                            "Groq stream %d: %s",
                                            resp.status_code, err[:300],
                                        )
                                        fb = self._fallback_response(request.message, context)
                                        full_text_parts.append(fb)
                                        yield StreamingChatResponse(
                                            chunk=fb,
                                            conversation_id=conversation_id,
                                            is_final=False,
                                        )
                                    else:
                                        async for line in resp.aiter_lines():
                                            if not line or not line.startswith("data: "):
                                                continue
                                            data = line[6:].strip()
                                            if data == "[DONE]":
                                                break
                                            try:
                                                obj = json.loads(data)
                                                delta = obj["choices"][0]["delta"].get("content", "")
                                            except (json.JSONDecodeError, KeyError, IndexError):
                                                continue
                                            if not delta:
                                                continue
                                            full_text_parts.append(delta)
                                            yield StreamingChatResponse(
                                                chunk=delta,
                                                conversation_id=conversation_id,
                                                is_final=False,
                                            )
                        except (httpx.TimeoutException, httpx.HTTPError) as exc:
                            logger.error("Groq streaming transport error: %s", exc)
                            fb = self._fallback_response(request.message, context)
                            full_text_parts.append(fb)
                            yield StreamingChatResponse(
                                chunk=fb,
                                conversation_id=conversation_id,
                                is_final=False,
                            )

                    full_text = "".join(full_text_parts)
                    try:
                        gen.update(output=full_text)
                    except Exception:  # noqa: BLE001
                        pass

                # 6. Optional medical-disclaimer suffix as one more chunk
                disclaimer = ""
                if full_text and (
                    "consult" not in full_text.lower()
                    and "healthcare professional" not in full_text.lower()
                ):
                    disclaimer = (
                        "\n\n💡 **Note:** For personalized medical advice, "
                        "please consult a healthcare professional."
                    )
                    yield StreamingChatResponse(
                        chunk=disclaimer,
                        conversation_id=conversation_id,
                        is_final=False,
                    )

                # 7. Final chunk carries sources + is_final marker
                yield StreamingChatResponse(
                    chunk="",
                    conversation_id=conversation_id,
                    is_final=True,
                    sources=sources,
                )

                # 8. Persist assembled assistant message
                final_text = full_text + disclaimer
                if final_text.strip():
                    await chat_repository.add_message(
                        db=db,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=final_text,
                    )

                try:
                    trace.update(output={
                        "response_length": len(final_text),
                        "n_sources": len(sources),
                    })
                except Exception:  # noqa: BLE001
                    pass

            except Exception as e:
                logger.error(f"Error in streaming response: {e}")
                yield StreamingChatResponse(
                    chunk="Error generating response.",
                    conversation_id=conversation_id,
                    is_final=True,
                    sources=[],
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
