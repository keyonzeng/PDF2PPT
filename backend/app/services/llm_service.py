import os
import json
from openai import OpenAI
from google import genai
from typing import Optional
from app.core.config import settings
from app.services.auth_service import get_valid_credentials

# Hybrid LLM Service
# - Gemini: Supports API Key OR Persistent OAuth
# - Others: OpenAI Compatible

def get_openai_client(provider: str) -> Optional[OpenAI]:
    if provider == "openai":
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    elif provider == "kimi":
        return OpenAI(
            api_key=settings.MOONSHOT_API_KEY,
            base_url="https://api.moonshot.cn/v1"
        )
    elif provider == "qwen":
        return OpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    return None

def generate_speaker_notes(text: str, provider: str = None, model: str = "") -> str:
    """Generate speaker notes using the specified provider and model."""
    if not text:
        return ""

    if not provider:
        provider = settings.LLM_PROVIDER
    
    # --- Gemini Strategy ---
    if provider == "gemini":
        try:
            client = None
            
            # 1. Try Persistent OAuth (via auth_service)
            creds = get_valid_credentials()
            if creds:
                client = genai.Client(credentials=creds)
            
            # 2. Fallback to API Key
            if not client and settings.GEMINI_API_KEY:
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
            if not client:
                return "Error: Gemini Auth Failed. No valid Token/Secret or API Key."

            target_model = model if model else settings.GEMINI_MODEL
            
            response = client.models.generate_content(
                model=target_model,
                contents=f"You are a helpful assistant. Generate conversational speaker notes for the following presentation slide text:\n\n{text}"
            )
            return response.text
        except Exception as e:
            print(f"LLM Error (Gemini): {e}")
            return ""

    # --- OpenAI Strategy ---
    try:
        client = get_openai_client(provider)
        if not client:
            return f"Error: Invalid Provider {provider}"

        target_model = model
        if not target_model:
            if provider == "openai": target_model = settings.OPENAI_MODEL
            elif provider == "kimi": target_model = settings.KIMI_MODEL
            elif provider == "qwen": target_model = settings.QWEN_MODEL
            else: target_model = "gpt-4o-mini"

        response = client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Generate speaker notes for a presentation slide based on the following text. Keep it conversational."},
                {"role": "user", "content": text}
            ],
            max_tokens=200
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"LLM Error ({provider}): {e}")
        return ""
