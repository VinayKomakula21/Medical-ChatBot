"""
Simple chat service with contextual responses using templates
Since HF free tier doesn't support most text generation models,
we'll use a template-based approach with context from Pinecone
"""
import logging
import time
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.exceptions import LLMException, VectorStoreException
from app.models.chat import ChatRequest, ChatResponse, StreamingChatResponse

logger = logging.getLogger(__name__)

class SimpleChatService:
    """
    Provides contextual responses using retrieved documents
    without relying on external LLM APIs
    """

    def __init__(self):
        self.response_templates = {
            "diabetes": {
                "definition": "Diabetes is a chronic metabolic disorder characterized by elevated blood glucose levels. There are two main types: Type 1 (insulin-dependent) where the pancreas produces little or no insulin, and Type 2 (non-insulin-dependent) where the body becomes resistant to insulin or doesn't produce enough.",
                "symptoms": "Common symptoms include: frequent urination, excessive thirst, unexplained weight loss, fatigue, blurred vision, slow-healing wounds, and recurring infections.",
                "treatment": "Treatment varies by type: Type 1 requires insulin therapy, while Type 2 can often be managed with lifestyle changes, oral medications, and sometimes insulin. All patients benefit from blood sugar monitoring, healthy diet, and regular exercise."
            },
            "hypertension": {
                "definition": "Hypertension (high blood pressure) is a condition where blood pressure in the arteries is persistently elevated above 130/80 mmHg. It's often called the 'silent killer' as it typically has no symptoms.",
                "symptoms": "Usually asymptomatic, but severe cases may cause headaches, shortness of breath, nosebleeds, and vision problems.",
                "treatment": "Treatment includes lifestyle modifications (reduced sodium intake, weight loss, exercise) and medications such as ACE inhibitors, beta-blockers, or diuretics."
            },
            "cancer": {
                "definition": "Cancer is a group of diseases involving abnormal cell growth with the potential to invade or spread to other parts of the body. There are over 100 types of cancer.",
                "symptoms": "Symptoms vary by type but may include: unexplained weight loss, fatigue, pain, skin changes, persistent cough, unusual bleeding, or lumps.",
                "treatment": "Treatment depends on type and stage, including surgery, chemotherapy, radiation therapy, immunotherapy, and targeted therapy."
            }
        }

    def _extract_topic(self, message: str) -> Optional[str]:
        """Extract medical topic from user message"""
        message_lower = message.lower()

        topics = {
            "diabetes": ["diabetes", "diabetic", "blood sugar", "glucose", "insulin"],
            "hypertension": ["hypertension", "blood pressure", "bp", "pressure"],
            "cancer": ["cancer", "tumor", "tumour", "oncology", "malignant"]
        }

        for topic, keywords in topics.items():
            if any(keyword in message_lower for keyword in keywords):
                return topic

        return None

    def _generate_contextual_response(self, message: str, context: str) -> str:
        """Generate response based on message and retrieved context"""
        message_lower = message.lower()

        # Check if the context is actually relevant to the question
        question_keywords = message_lower.split()
        context_lower = context.lower() if context else ""

        # Check if key terms from question appear in context
        relevance_score = sum(1 for keyword in question_keywords
                             if len(keyword) > 3 and keyword in context_lower)

        # If context is not relevant enough, provide a generic response
        if relevance_score < 1 and context:
            # Context doesn't match the question well
            if "acne" in message_lower:
                base_response = "Acne is a common skin condition that occurs when hair follicles become clogged with oil and dead skin cells. Precautions include: maintaining good skin hygiene, avoiding touching your face frequently, using non-comedogenic products, eating a healthy diet, and managing stress levels."
            elif "precaution" in message_lower or "prevent" in message_lower:
                base_response = f"For {message.split()[2] if len(message.split()) > 2 else 'this condition'}, general precautions include maintaining good hygiene, following a healthy lifestyle, and consulting with healthcare professionals for specific guidance."
            else:
                base_response = f"I couldn't find specific information about '{message}' in the available medical database. Please consult a healthcare professional for accurate information about this topic."
        else:
            # Extract topic
            topic = self._extract_topic(message)

            # Determine question type
            if any(word in message_lower for word in ["what is", "define", "definition", "explain"]):
                question_type = "definition"
            elif any(word in message_lower for word in ["symptom", "sign", "feel", "experience"]):
                question_type = "symptoms"
            elif any(word in message_lower for word in ["treat", "cure", "manage", "therapy", "medication", "precaution"]):
                question_type = "treatment"
            else:
                question_type = "general"

            # Generate response
            if topic and question_type in self.response_templates.get(topic, {}):
                base_response = self.response_templates[topic][question_type]
            else:
                # Use context only if it's relevant
                if context and relevance_score >= 1:
                    # Extract the most relevant part of context
                    sentences = context.split('.')
                    relevant_sentences = [s for s in sentences
                                        if any(k in s.lower() for k in question_keywords if len(k) > 3)]
                    if relevant_sentences:
                        # Use more context for detailed responses
                        base_response = f"Based on the medical information available: {'. '.join(relevant_sentences[:5])}."
                    else:
                        # Use more context - up to 1500 characters for detailed answers
                        base_response = f"Based on the medical information available:\n\n{context[:1500]}"
                else:
                    base_response = f"I couldn't find specific information about '{message}' in the available medical database. Please consult a healthcare professional for accurate information."

        # Add disclaimer
        disclaimer = "\n\nNote: This information is for educational purposes only. Please consult a healthcare professional for medical advice."

        return base_response + disclaimer

    async def generate_response(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        start_time = time.time()
        conversation_id = request.conversation_id or uuid4()

        try:
            logger.info(f"Processing chat request: {request.message[:100]}...")

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
                    # Combine top results for context
                    context = "\n\n".join([result["content"] for result in search_results[:2]])
                    logger.info(f"Found {len(sources)} relevant documents")
                else:
                    logger.info("No relevant documents found")

            except Exception as e:
                logger.warning(f"Could not search documents: {e}")
                # Continue without context

            # Generate contextual response
            response_text = self._generate_contextual_response(request.message, context)

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
        """Generate streaming response"""
        conversation_id = request.conversation_id or uuid4()

        try:
            # Generate full response
            response = await self.generate_response(request)

            # Simulate streaming
            chunk_size = 20
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

                await asyncio.sleep(0.02)

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
        return []

    async def clear_conversation(
        self,
        conversation_id: UUID
    ) -> bool:
        return True

# Use the simple service for now
chat_service = SimpleChatService()