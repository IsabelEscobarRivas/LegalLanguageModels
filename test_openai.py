"""
Test OpenAI client functionality
"""
import asyncio
import os
from dotenv import load_dotenv  # Make sure this import is here

# Load environment variables from .env file
load_dotenv()  # This will now work after the import

from app.services.llm_client import get_openai_client

async def test_openai():
    client = get_openai_client()
    try:
        # Test simple text generation
        response = await client.generate_text(
            "What are the requirements for an EB1 visa?",
            system_message="You are an immigration expert. Keep your response brief (2-3 sentences)."
        )
        print("OpenAI Response:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        print("Test completed successfully!")
    finally:
        await client.close()

if __name__ == "__main__":
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable")
        exit(1)
    
    # Run the test
    asyncio.run(test_openai())