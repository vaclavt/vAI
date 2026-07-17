from abc import ABC, abstractmethod
from typing import Dict, Any
import json


class AIEndpointHandler(ABC):
    """Abstract base class for AI endpoint handlers."""

    def __init__(self, assistant_role: str):
        self.assistant_role = assistant_role

    @abstractmethod
    def prepare_payload(self, prompt: str, model: str) -> Dict[str, Any]:
        """Prepare the payload for the specific API."""
        pass

    @abstractmethod
    def process_response(self, line: str) -> Dict[str, Any]:
        """Process a response line from the API."""
        pass

    def get_token_header(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"} if token else {}


class OpenAIHandler(AIEndpointHandler):
    """Handler for OpenAI API endpoint."""

    def __init__(self, assistant_role: str):
        super().__init__(assistant_role)

    def prepare_payload(self, prompt: str, model: str) -> Dict[str, Any]:
        """Prepare and return payload for API request."""
        return {
            "model": model,
            "messages": [{"role": "system", "content": self.assistant_role}, {"role": "user", "content": prompt}],
            "stream": True,
        }

    def process_response(self, line: str) -> Dict[str, Any]:
        # Handle different response formats
        if line.startswith("data: "):
            line = line[6:]  # Remove "data: " prefix for OpenAI format

        # Check for end of stream markers
        if line.strip() == "[DONE]":
            return {"response": "", "done": True}

        # Handle empty lines
        if not line.strip():
            return {"response": "", "done": False}

        try:
            data = json.loads(line)

            # Standard OpenAI format
            if "choices" in data:
                content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                finish_reason = data.get("choices", [{}])[0].get("finish_reason")
                return {"response": content, "done": finish_reason == "stop"}

            # Fallback for other formats (e.g., simple text response)
            elif "response" in data:
                return {"response": data["response"], "done": data.get("done", False)}

            # If we can't parse the expected format, try to extract content from common fields
            else:
                # Try to find content in various possible fields
                content = ""
                if "content" in data:
                    content = data["content"]
                elif "text" in data:
                    content = data["text"]
                elif "message" in data and isinstance(data["message"], str):
                    content = data["message"]

                # Try to determine if this is the end
                done = data.get("done", False) or data.get("finish_reason") == "stop"
                return {"response": content, "done": done}

        except json.JSONDecodeError:
            # If JSON parsing fails, return empty response but don't mark as done
            # This allows the stream to continue
            return {"response": "", "done": False}
