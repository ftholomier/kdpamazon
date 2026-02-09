#!/usr/bin/env python3

import os
import sys
import asyncio
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

async def test_llm_integration():
    """Test different model names and configurations"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    # Get API key from environment
    api_key = os.environ.get('EMERGENT_LLM_KEY', '')
    if not api_key:
        print("❌ EMERGENT_LLM_KEY not found in environment")
        return False
    
    print(f"🔑 Using API key: {api_key[:10]}...")
    
    # Test different model configurations
    test_configs = [
        ("gemini", "gemini-2.5-flash-lite"),
        ("gemini", "gemini-2.0-flash-experimental"),
        ("gemini", "gemini-1.5-flash"),
        ("gemini", "gemini-pro"),
        ("openai", "gpt-4o"),
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
    ]
    
    for provider, model in test_configs:
        print(f"\n🧪 Testing {provider}/{model}...")
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id="test-session",
                system_message="You are a test assistant."
            )
            
            chat.with_model(provider, model)
            
            msg = UserMessage(text="Say 'hello' in one word.")
            response = await chat.send_message(msg)
            
            print(f"✅ SUCCESS: {provider}/{model}")
            print(f"   Response: {response[:50]}...")
            return True, provider, model
            
        except Exception as e:
            print(f"❌ FAILED: {provider}/{model} - {str(e)[:100]}")
            continue
    
    print("\n❌ No working model configuration found!")
    return False, None, None

async def main():
    print("🚀 Testing LLM Integration...")
    print("=" * 50)
    
    # Load environment variables
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / "backend" / ".env"
    load_dotenv(env_path)
    
    success, working_provider, working_model = await test_llm_integration()
    
    if success:
        print(f"\n🎉 Found working configuration: {working_provider}/{working_model}")
        print("✅ LLM integration is working!")
        return 0
    else:
        print("\n💥 LLM integration is broken!")
        print("🔧 Need to fix the model configuration in backend/server.py")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)