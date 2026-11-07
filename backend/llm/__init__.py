"""Text generation, behind one interface, across every major provider.

The app's only LLM use is optional - classifying a government form's fields
from its extracted text when the rule-based extractor is not enough. It must
not be tied to one vendor, so every model sits behind an `LlmProvider` with the
same `complete()`, selected and failed-over by a registry exactly like the
speech layer.

Providers, all over plain HTTPS (no vendor SDKs, so the backend runs anywhere):

  NVIDIA NIM, OpenAI, Anthropic, Google Gemini, Groq, Mistral, DeepSeek,
  Together, Fireworks, Cohere, Ollama (local), any OpenAI-compatible server,
  the bundled Emergent key, and a mock for tests.

Add a key in the environment and the provider becomes available; nothing else
changes. `GET /api/llm/providers` lists what is configured and the order it
will be tried.
"""
