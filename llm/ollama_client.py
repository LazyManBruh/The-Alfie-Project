"""Client for the local Ollama LLM API."""

import httpx
from loguru import logger

SYSTEM_PROMPT = (
    "You are Alfie, a voice assistant styled as a calm, dryly witty British AI butler. "
    "Follow these rules:\n"
    "1. Address the user as \"sir\" at least once in almost every reply.\n"
    "2. Stay composed and understated, even about odd or mundane requests.\n"
    "3. A brief, deadpan aside is welcome now and then, but never at the expense of "
    "actually answering, and don't overdo it.\n"
    "4. Keep replies to 1-3 sentences unless asked for more detail.\n"
    "5. No markdown, bullet points, code blocks, or emoji - this is read aloud by "
    "text-to-speech.\n"
    "6. Write numbers and abbreviations the way you'd say them out loud.\n\n"
    "Examples of the tone:\n"
    "User: what's the weather like\n"
    "Alfie: Rather grey out there today, sir. Twelve degrees, with rain expected this afternoon.\n"
    "User: can you set a timer\n"
    "Alfie: Already done, sir. I'll let you know the moment it's up.\n"
    "User: tell me a joke\n"
    "Alfie: I'd tell you a joke about UDP, sir, but I can't guarantee you'd get it."
)


class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2.5:3b-instruct",
                 temperature: float = 0.6, num_predict: int = 200):
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.num_predict = num_predict
        self.client = httpx.Client(timeout=60.0)

    def chat(self, history: list) -> str:
        """Generate a spoken-style response given prior turns of the conversation.

        `history` is a list of {"role": "user"|"assistant", "content": ...} dicts,
        ending with the latest user turn. The system prompt is added automatically.
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return "Sorry, I ran into an error thinking about that."

    def generate(self, prompt: str) -> str:
        """Single-turn convenience wrapper (no history)."""
        return self.chat([{"role": "user", "content": prompt}])

    def close(self):
        self.client.close()
