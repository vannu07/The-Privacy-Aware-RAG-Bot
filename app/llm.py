"""
LLM Integration for RAG (Retrieval-Augmented Generation)
Supports multiple providers: OpenAI, Anthropic, or local models
"""

import os
from typing import List, Dict, Any
from .models import Document, ConversationMessage, LLMResponse

# Try importing LLM libraries (optional dependencies)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMClient:
    """
    LLM client for generating answers from retrieved documents.
    Configurable via environment variables:
    - LLM_PROVIDER: 'openai', 'anthropic', or 'mock' (default: mock)
    - OPENAI_API_KEY: OpenAI API key
    - ANTHROPIC_API_KEY: Anthropic API key
    - LLM_MODEL: Model name (default: gpt-4 or claude-3-sonnet)
    """
    
    def __init__(self):
        self.provider = os.getenv('LLM_PROVIDER', 'mock').lower()
        self.model = os.getenv('LLM_MODEL')
        
        if self.provider == 'openai':
            if not OPENAI_AVAILABLE:
                raise ImportError("openai package not installed. Run: pip install openai")
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable required")
            self.client = openai.OpenAI(api_key=api_key)
            self.model = self.model or 'gpt-4-turbo-preview'
            
        elif self.provider == 'anthropic':
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable required")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = self.model or 'claude-3-sonnet-20240229'
            
        else:  # mock provider
            self.client = None
            self.model = 'mock'
    
    def generate_answer(self, query: str, documents: List[Document], 
                       conversation_history: List[ConversationMessage] = None) -> LLMResponse:
        """
        Generate an answer using RAG:
        1. Build context from retrieved documents
        2. Include conversation history if available
        3. Generate answer with citations
        """
        
        # Build context from documents
        context = self._build_context(documents)
        
        # Build conversation context
        conv_context = self._build_conversation_context(conversation_history) if conversation_history else ""
        
        # Create system prompt
        system_prompt = self._get_system_prompt()
        
        # Create user prompt with context and query
        user_prompt = f"""Context from knowledge base:
{context}

{conv_context}

Question: {query}

Please provide a comprehensive answer based on the context provided. Include citations using [doc_id] format."""
        
        if self.provider == 'openai':
            return self._generate_openai(system_prompt, user_prompt, documents)
        elif self.provider == 'anthropic':
            return self._generate_anthropic(system_prompt, user_prompt, documents)
        else:
            return self._generate_mock(query, documents)
    
    def _build_context(self, documents: List[Document]) -> str:
        """Build context string from documents"""
        context_parts = []
        for doc in documents:
            context_parts.append(f"[{doc.id}] {doc.title}\n{doc.content}")
        return "\n\n".join(context_parts)
    
    def _build_conversation_context(self, history: List[ConversationMessage]) -> str:
        """Build conversation history context"""
        if not history:
            return ""
        conv_parts = ["Previous conversation:"]
        for msg in history[-5:]:  # Last 5 messages
            role = msg.role.upper()
            conv_parts.append(f"{role}: {msg.content}")
        return "\n".join(conv_parts) + "\n"
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the LLM"""
        return """You are a helpful AI assistant with access to a knowledge base. 
Your task is to answer questions based on the provided context documents.
- Always cite your sources using [doc_id] format
- If the answer is not in the context, say so
- Be concise and accurate
- Respect document sensitivity - if a document is marked sensitive, treat the information carefully"""
    
    def _generate_openai(self, system_prompt: str, user_prompt: str, 
                        documents: List[Document]) -> LLMResponse:
        """Generate answer using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            citations = self._extract_citations(answer, documents)
            confidence = self._estimate_confidence(response)
            
            return LLMResponse(
                answer=answer,
                confidence=confidence,
                citations=citations
            )
        except Exception as e:
            return LLMResponse(
                answer=f"Error generating answer: {str(e)}",
                confidence=0.0,
                citations=[]
            )
    
    def _generate_anthropic(self, system_prompt: str, user_prompt: str, 
                           documents: List[Document]) -> LLMResponse:
        """Generate answer using Anthropic Claude"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            answer = response.content[0].text
            citations = self._extract_citations(answer, documents)
            confidence = 0.8  # Anthropic doesn't provide confidence scores
            
            return LLMResponse(
                answer=answer,
                confidence=confidence,
                citations=citations
            )
        except Exception as e:
            return LLMResponse(
                answer=f"Error generating answer: {str(e)}",
                confidence=0.0,
                citations=[]
            )
    
    def _generate_mock(self, query: str, documents: List[Document]) -> LLMResponse:
        """Generate mock answer for testing"""
        if not documents:
            answer = f"I don't have any information to answer: {query}"
            return LLMResponse(answer=answer, confidence=0.0, citations=[])
        
        # Create a simple mock answer
        doc_summaries = []
        citations = []
        for doc in documents[:3]:  # Use top 3 docs
            doc_summaries.append(f"According to [{doc.id}], {doc.title}: {doc.content[:100]}...")
            citations.append(doc.id)
        
        answer = f"Based on the available documents:\n\n" + "\n\n".join(doc_summaries)
        
        return LLMResponse(
            answer=answer,
            confidence=0.7,
            citations=citations
        )
    
    def _extract_citations(self, answer: str, documents: List[Document]) -> List[str]:
        """Extract document IDs mentioned in the answer"""
        citations = []
        for doc in documents:
            if f"[{doc.id}]" in answer or doc.id in answer:
                citations.append(doc.id)
        return citations
    
    def _estimate_confidence(self, response) -> float:
        """Estimate confidence from OpenAI response"""
        # Simple heuristic: longer responses with citations tend to be more confident
        # In production, you might use logprobs or other signals
        return 0.8


def get_llm_client() -> LLMClient:
    """Factory function to get configured LLM client"""
    return LLMClient()
