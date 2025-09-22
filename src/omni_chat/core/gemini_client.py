import os
from typing import Optional
from google import genai
from dotenv import load_dotenv

class GeminiClient:
    """A client for interacting with the Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini client with an optional API key.
        
        Args:
            api_key: Optional API key. If not provided, will look for GEMINI_API_KEY in environment.
        """
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response from the Gemini model.
        
        Args:
            prompt: The user's input prompt
            
        Returns:
            The generated response text
        """
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json'
                }
            )
            return response.text.strip()
        except Exception as e:
            return f"Error generating response: {str(e)}"
