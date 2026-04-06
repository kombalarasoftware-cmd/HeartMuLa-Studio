import requests
import logging
from typing import List, Optional, Dict, Any
import json
import os
import uuid

logger = logging.getLogger(__name__)

import random

MUSIC_STYLES_LIBRARY = [
    "Cinematic", "Lo-fi", "Synthwave", "Rock", "HipHop", "Orchestral", "Ambient", "Trap", "Techno",
    "Jazz", "Blues", "Country", "Folk", "Reggae", "Soul", "R&B", "Funk", "Disco", "House", "Trance",
    "Dubstep", "Drum & Bass", "Jungle", "Garage", "Grime", "Afrobeats", "K-Pop", "J-Pop", "Indie Pop",
    "Dream Pop", "Shoegaze", "Post-Rock", "Math Rock", "Prog Rock", "Metal", "Punk", "Emo", "Grunge",
    "Acoustic", "Piano", "Classical", "Opera", "Gregorian Chant", "Medieval", "Celtic", "Nordic Folk",
    "Latin", "Salsa", "Bossa Nova", "Reggaeton", "Flamenco", "Tango", "Bollywood", "Indian Classical",
    "Gospel", "Spiritual", "Meditative", "New Age", "Dark Ambient", "Drone", "Noise", "Industrial",
    "Cyberpunk", "Vaporwave", "Chiptune", "Glitch", "IDM", "Complextro", "Electro Swing", "Nu-Disco",
    "Future Bass", "Tropical House", "Deep House", "Tech House", "Acid House", "Psytrance", "Hardstyle",
    "Breakbeat", "Trip-Hop", "Downtempo", "Chillout", "Lounge", "Elevator Music", "Muzak", "Experimental",
    "Avant-Garde", "Musique Concrete", "Minimalism", "Baroque", "Renaissance", "Romantic", "Impressionist"
]

SUPPORTED_LANGUAGES = [
    "English", "Spanish", "French", "German", "Italian", "Portuguese", "Romanian", "Russian",
    "Japanese", "Korean", "Chinese", "Arabic", "Hindi", "Turkish", "Dutch", "Polish",
    "Swedish", "Danish", "Norwegian", "Finnish", "Greek", "Hebrew", "Thai", "Vietnamese"
]

# ============== Provider Data Model ==============

def _make_provider_id() -> str:
    return str(uuid.uuid4())[:8]


def _default_providers_from_env() -> List[Dict[str, Any]]:
    """Build initial providers list from environment variables (backward compat)."""
    providers = []

    # Ollama from env
    ollama_host = os.environ.get("OLLAMA_HOST", "")
    if ollama_host:
        providers.append({
            "id": "ollama-default",
            "name": "Ollama (Local)",
            "type": "ollama",
            "base_url": ollama_host,
            "api_key": "",
            "enabled": True,
            "models": [],
            "enabled_models": []
        })

    # Custom API from env (OpenAI, vLLM, etc.)
    custom_base = os.environ.get("CUSTOM_API_BASE_URL", "")
    custom_key = os.environ.get("CUSTOM_API_KEY", "")
    custom_model = os.environ.get("CUSTOM_API_MODEL", "")
    if custom_base:
        providers.append({
            "id": "custom-default",
            "name": _provider_name_from_url(custom_base),
            "type": "openai",
            "base_url": custom_base,
            "api_key": custom_key,
            "enabled": True,
            "models": [{"id": custom_model, "name": custom_model}] if custom_model else [],
            "enabled_models": [custom_model] if custom_model else []
        })

    # OpenRouter from env
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        providers.append({
            "id": "openrouter-default",
            "name": "OpenRouter",
            "type": "openai",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": openrouter_key,
            "enabled": True,
            "models": [],
            "enabled_models": []
        })

    return providers


def _provider_name_from_url(url: str) -> str:
    """Guess a friendly name from a base URL."""
    url_lower = url.lower()
    if "openai.com" in url_lower:
        return "OpenAI"
    if "openrouter.ai" in url_lower:
        return "OpenRouter"
    if "anthropic.com" in url_lower:
        return "Anthropic"
    if "localhost" in url_lower or "127.0.0.1" in url_lower:
        return "Local API"
    if "host.docker.internal" in url_lower:
        return "Host API"
    # Extract hostname
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or "Custom"
        return hostname.split(".")[0].capitalize()
    except Exception:
        return "Custom API"


class LLMService:
    """Multi-provider LLM service.

    Supports two provider types:
    - "openai": Any OpenAI-compatible API (OpenAI, OpenRouter, vLLM, LM Studio, etc.)
    - "ollama": Ollama API (different request format)

    Provider data structure:
    {
        "id": "abc123",
        "name": "OpenAI",
        "type": "openai" | "ollama",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-...",
        "enabled": true,
        "models": [{"id": "gpt-4o-mini", "name": "GPT-4o Mini"}, ...],
        "enabled_models": ["gpt-4o-mini", "gpt-4.1-mini"]
    }
    """

    # Runtime provider list
    _providers: List[Dict[str, Any]] = []

    @classmethod
    def init_providers(cls, saved_providers: List[Dict[str, Any]] = None):
        """Initialize providers from saved data or environment."""
        if saved_providers:
            cls._providers = saved_providers
        else:
            cls._providers = _default_providers_from_env()
        logger.info(f"[LLM] Initialized {len(cls._providers)} provider(s)")

    @classmethod
    def get_providers(cls) -> List[Dict[str, Any]]:
        """Return all providers (API keys masked)."""
        result = []
        for p in cls._providers:
            masked = dict(p)
            key = masked.get("api_key", "")
            masked["api_key"] = f"***{key[-4:]}" if key and len(key) > 4 else ""
            result.append(masked)
        return result

    @classmethod
    def get_providers_raw(cls) -> List[Dict[str, Any]]:
        """Return all providers with raw (unmasked) API keys — for persistence only."""
        return cls._providers

    @classmethod
    def add_provider(cls, name: str, provider_type: str, base_url: str,
                     api_key: str = "") -> Dict[str, Any]:
        """Add a new provider."""
        provider = {
            "id": _make_provider_id(),
            "name": name or _provider_name_from_url(base_url),
            "type": provider_type,
            "base_url": base_url.rstrip("/"),
            "api_key": api_key,
            "enabled": True,
            "models": [],
            "enabled_models": []
        }
        cls._providers.append(provider)
        logger.info(f"[LLM] Added provider: {provider['name']} ({provider['type']})")
        return provider

    @classmethod
    def update_provider(cls, provider_id: str, **kwargs) -> Dict[str, Any]:
        """Update an existing provider's fields."""
        for p in cls._providers:
            if p["id"] == provider_id:
                for key, val in kwargs.items():
                    if key in p and val is not None:
                        if key == "base_url":
                            p[key] = val.rstrip("/")
                        else:
                            p[key] = val
                logger.info(f"[LLM] Updated provider: {p['name']}")
                return p
        raise ValueError(f"Provider not found: {provider_id}")

    @classmethod
    def delete_provider(cls, provider_id: str) -> bool:
        """Delete a provider."""
        before = len(cls._providers)
        cls._providers = [p for p in cls._providers if p["id"] != provider_id]
        deleted = len(cls._providers) < before
        if deleted:
            logger.info(f"[LLM] Deleted provider: {provider_id}")
        return deleted

    @classmethod
    def fetch_models(cls, provider_id: str) -> List[Dict[str, str]]:
        """Fetch available models from a provider's API."""
        provider = cls._get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider not found: {provider_id}")

        models = []
        if provider["type"] == "ollama":
            models = cls._fetch_ollama_models(provider)
        else:
            models = cls._fetch_openai_models(provider)

        # Update the provider's model list
        provider["models"] = models
        logger.info(f"[LLM] Fetched {len(models)} models from {provider['name']}")
        return models

    @classmethod
    def toggle_model(cls, provider_id: str, model_id: str, enabled: bool) -> bool:
        """Enable or disable a model for a provider."""
        provider = cls._get_provider(provider_id)
        if not provider:
            return False

        enabled_models = set(provider.get("enabled_models", []))
        if enabled:
            enabled_models.add(model_id)
        else:
            enabled_models.discard(model_id)
        provider["enabled_models"] = list(enabled_models)
        return True

    @classmethod
    def get_active_models(cls) -> List[Dict[str, Any]]:
        """Get all enabled models across all enabled providers.
        Returns list of {id, name, provider_id, provider_name, provider_type}.
        """
        models = []
        for p in cls._providers:
            if not p.get("enabled", True):
                continue
            enabled_models = set(p.get("enabled_models", []))
            for m in p.get("models", []):
                if m["id"] in enabled_models:
                    models.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "provider_id": p["id"],
                        "provider_name": p["name"],
                        "provider_type": p["type"]
                    })
        return models

    # ============== Model Fetching (Internal) ==============

    @classmethod
    def _fetch_ollama_models(cls, provider: Dict) -> List[Dict[str, str]]:
        """Fetch models from Ollama API."""
        try:
            resp = requests.get(f"{provider['base_url']}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {"id": m["name"], "name": m["name"]}
                    for m in data.get("models", [])
                ]
        except Exception as e:
            logger.warning(f"[LLM] Failed to fetch Ollama models: {e}")
        return []

    @classmethod
    def _fetch_openai_models(cls, provider: Dict) -> List[Dict[str, str]]:
        """Fetch models from OpenAI-compatible /v1/models endpoint."""
        base_url = provider["base_url"].rstrip("/")
        headers = {"Content-Type": "application/json"}
        if provider.get("api_key"):
            headers["Authorization"] = f"Bearer {provider['api_key']}"

        try:
            resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", [])
                # Sort by id and return
                models = []
                for m in raw_models:
                    model_id = m.get("id", "")
                    # Skip internal/system models
                    if model_id.startswith("ft:") or model_id.startswith("dall-e"):
                        continue
                    models.append({
                        "id": model_id,
                        "name": m.get("name", model_id)
                    })
                models.sort(key=lambda x: x["id"])
                return models
        except Exception as e:
            logger.warning(f"[LLM] Failed to fetch models from {provider['name']}: {e}")
        return []

    # ============== LLM Call Routing ==============

    @classmethod
    def _get_provider(cls, provider_id: str) -> Optional[Dict]:
        """Get a provider by ID."""
        for p in cls._providers:
            if p["id"] == provider_id:
                return p
        return None

    @classmethod
    def _call_llm(cls, model_id: str, prompt: str, provider_id: str,
                   json_mode: bool = False, temperature: float = 0.7) -> str:
        """Unified LLM call — routes to the correct provider."""
        provider = cls._get_provider(provider_id)
        if not provider:
            raise ValueError(f"Provider not found: {provider_id}")

        if provider["type"] == "ollama":
            return cls._call_ollama(provider, model_id, prompt, json_mode, temperature)
        else:
            return cls._call_openai_compat(provider, model_id, prompt, temperature)

    @classmethod
    def _call_ollama(cls, provider: Dict, model: str, prompt: str,
                     json_mode: bool = False, temperature: float = 0.7) -> str:
        """Call Ollama API."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }
        if json_mode:
            payload["format"] = "json"

        resp = requests.post(
            f"{provider['base_url']}/api/generate",
            json=payload,
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
        raise Exception(f"Ollama Error: {resp.text}")

    @classmethod
    def _call_openai_compat(cls, provider: Dict, model: str, prompt: str,
                            temperature: float = 0.7) -> str:
        """Call any OpenAI-compatible API (OpenAI, OpenRouter, vLLM, etc.)."""
        base_url = provider["base_url"].rstrip("/")
        headers = {"Content-Type": "application/json"}
        if provider.get("api_key"):
            headers["Authorization"] = f"Bearer {provider['api_key']}"

        # OpenRouter-specific headers
        if "openrouter.ai" in base_url.lower():
            headers["HTTP-Referer"] = "http://localhost:5173"
            headers["X-Title"] = "HeartMuLa Music"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        raise Exception(f"{provider['name']} Error: {resp.status_code} - {resp.text}")

    # ============== Backward Compat: find provider for a model ==============

    @classmethod
    def _find_provider_for_model(cls, model_id: str, provider_id: str = None) -> Optional[Dict]:
        """Find the provider that has this model enabled.
        If provider_id is given, use it directly. Otherwise search."""
        if provider_id:
            return cls._get_provider(provider_id)
        # Search enabled providers
        for p in cls._providers:
            if not p.get("enabled", True):
                continue
            enabled_models = set(p.get("enabled_models", []))
            if model_id in enabled_models:
                return p
            # Also check models list
            for m in p.get("models", []):
                if m["id"] == model_id:
                    return p
        return None

    # ============== High-Level Generation Functions ==============

    @staticmethod
    def get_supported_languages() -> List[str]:
        return SUPPORTED_LANGUAGES

    @staticmethod
    def generate_lyrics(topic: str, model: str = "llama3", seed_lyrics: Optional[str] = None,
                       provider_id: str = "", language: str = "English",
                       duration_seconds: Optional[int] = None) -> dict:
        """Generate lyrics and also suggest a refined topic and musical style."""

        provider = LLMService._find_provider_for_model(model, provider_id)
        if not provider:
            raise Exception(f"No provider found for model '{model}'. Please configure a provider in Settings.")

        # Build language instruction with diacritics requirement
        if language != "English":
            language_instruction = (
                f"Write the lyrics in {language}. "
                f"IMPORTANT: Use proper diacritics and special characters native to {language}. "
                f"For example: Romanian uses ă, â, î, ș, ț; French uses é, è, ê, ë, ç, à, ù; "
                f"German uses ä, ö, ü, ß; Spanish uses á, é, í, ó, ú, ñ, ü; Portuguese uses ã, õ, ç, á, é, etc. "
                f"Always use the correct native characters, never substitute with ASCII equivalents."
            )
        else:
            language_instruction = ""

        # Build duration-aware structure instruction
        duration_instruction = ""
        if duration_seconds and duration_seconds > 0:
            if duration_seconds <= 30:
                duration_instruction = (
                    f"\nSONG DURATION: {duration_seconds} seconds (very short).\n"
                    "STRUCTURE: Write a very concise song. Use only:\n"
                    "  [Intro] (2-4 sec, instrumental or 1 line)\n"
                    "  [Verse] (10-12 sec)\n"
                    "  [Chorus] (10-12 sec)\n"
                    "  [Outro] (2-4 sec, fade out feel, final line or hum)\n"
                    "Keep lyrics SHORT — few lines per section. The song must feel COMPLETE within this duration.\n"
                    "The [Outro] must give a sense of natural ending (repeat a key phrase, slow down, or fade).\n"
                )
            elif duration_seconds <= 60:
                duration_instruction = (
                    f"\nSONG DURATION: {duration_seconds} seconds (short single).\n"
                    "STRUCTURE: Plan the song to naturally fill ~{duration_seconds} seconds:\n"
                    "  [Intro] (4-6 sec, set the mood)\n"
                    "  [Verse] (12-15 sec)\n"
                    "  [Chorus] (12-15 sec)\n"
                    "  [Verse 2] (12-15 sec)\n"
                    "  [Outro] (4-8 sec, bring closure — repeat hook, fade, or final statement)\n"
                    "Keep sections concise. The song must feel COMPLETE — the [Outro] should wrap up naturally, "
                    "not feel like an abrupt cut. Use a fading repetition, a final reflection, or a soft ending.\n"
                )
            elif duration_seconds <= 120:
                duration_instruction = (
                    f"\nSONG DURATION: {duration_seconds} seconds (~2 minutes).\n"
                    "STRUCTURE: Plan a well-paced song for ~{duration_seconds} seconds:\n"
                    "  [Intro] (6-10 sec)\n"
                    "  [Verse] (15-20 sec)\n"
                    "  [Chorus] (15-20 sec)\n"
                    "  [Verse 2] (15-20 sec)\n"
                    "  [Chorus] (15-20 sec)\n"
                    "  [Bridge] (10-15 sec)\n"
                    "  [Outro] (8-12 sec, satisfying conclusion)\n"
                    "The [Outro] MUST provide a natural ending — repeat the hook softly, add a final reflection line, "
                    "or use 'ooh/ahh/na na na' to fade out. Never end abruptly.\n"
                )
            else:
                duration_instruction = (
                    f"\nSONG DURATION: {duration_seconds} seconds (~{duration_seconds // 60} minutes, full song).\n"
                    "STRUCTURE: Write a full, professionally structured song for ~{duration_seconds} seconds:\n"
                    "  [Intro] (8-15 sec, instrumental or vocal warmup)\n"
                    "  [Verse] (20-25 sec)\n"
                    "  [Pre-Chorus] (8-12 sec, optional but recommended for build-up)\n"
                    "  [Chorus] (20-25 sec)\n"
                    "  [Verse 2] (20-25 sec)\n"
                    "  [Chorus] (20-25 sec)\n"
                    "  [Bridge] (15-20 sec, contrast/key change/emotional shift)\n"
                    "  [Chorus] (20-25 sec, final powerful delivery)\n"
                    "  [Outro] (10-20 sec, graceful ending — fade, callback to intro, or final emotional note)\n"
                    "Write enough lyrics for each section to fill the time naturally. "
                    "The [Outro] MUST wrap the song up — use repeated hooks fading out, a reflective final line, "
                    "or instrumental cues like '(music fades)'. The song should feel like it was PLANNED to be this length.\n"
                )

        if seed_lyrics and seed_lyrics.strip():
            prompt = (
                f"Continue and complete these song lyrics. Topic/Context: {topic}.\n"
                f"{language_instruction}"
                f"{duration_instruction}\n\n"
                f"EXISTING LYRICS (Keep these exactly as is, and append the rest):\n"
                f"'''{seed_lyrics}'''\n\n"
                "RULES:\n"
                "- Keep the existing lyrics at the start\n"
                "- Complete with full song structure using [Intro], [Verse], [Chorus], [Bridge], [Outro] tags\n"
                "- The song MUST end with [Outro] that provides a natural, satisfying conclusion\n"
                "- If an artist name is mentioned (Drake, Taylor Swift, Eminem, etc.), match their lyrical style\n"
                "- OUTPUT ONLY THE LYRICS - no explanations, no analysis, no commentary\n"
                "- Start your response directly with [Intro] or the first section tag\n"
            )
        else:
            prompt = (
                f"Write song lyrics about: {topic}\n"
                f"{language_instruction}"
                f"{duration_instruction}\n\n"
                "RULES:\n"
                "- Use section tags: [Intro], [Verse], [Verse 2], [Chorus], [Bridge], [Outro]\n"
                "- The song MUST end with [Outro] that provides a natural, satisfying conclusion\n"
                "- The [Outro] should make the listener feel the song is intentionally ending (not cut off)\n"
                "- If an artist name is mentioned (Drake, Taylor Swift, Eminem, Travis Scott, etc.), write in their signature style\n"
                "- OUTPUT ONLY THE LYRICS - absolutely no explanations, analysis, or commentary\n"
                "- Start your response directly with [Intro] or the first section tag\n"
                "- Do not explain what style you're using, just write the lyrics\n"
            )

        try:
            is_ollama = provider["type"] == "ollama"
            lyrics = LLMService._call_llm(model, prompt, provider["id"])

            # Now generate suggested topic and style based on the lyrics
            style_prompt = (
                f"Based on these song lyrics and the original user request, suggest:\n"
                f"1. A refined, evocative song concept/topic (1 sentence)\n"
                f"2. Musical style tags (3-5 comma-separated tags like genre, mood, tempo, artist-style if applicable)\n\n"
                f"ORIGINAL USER REQUEST: {topic}\n\n"
                f"LYRICS:\n{lyrics[:500]}...\n\n"
                "IMPORTANT: If the user mentioned an artist name (e.g., 'like Drake', 'Taylor Swift style', 'Eminem'), "
                "include that artist's typical genre/style in the tags (e.g., 'Drake-style R&B', 'Taylor Swift Pop', 'Eminem Rap').\n\n"
                "Return ONLY a JSON object with 'topic' and 'tags' keys. No markdown, no explanation.\n"
                'Example: {"topic": "A bittersweet summer romance fading with autumn", "tags": "Pop, Melancholic, Acoustic, Mid-tempo"}\n'
                'Example with artist: {"topic": "Late night confessions in the city", "tags": "Drake-style R&B, Emotional, Melodic, Hip-Hop"}'
            )

            try:
                style_response = LLMService._call_llm(model, style_prompt, provider["id"],
                                                       json_mode=is_ollama)
                style_response = style_response.strip()
                if style_response.startswith("```"):
                    style_response = style_response.replace("```json", "").replace("```", "").strip()

                style_data = json.loads(style_response)
                return {
                    "lyrics": lyrics,
                    "suggested_topic": style_data.get("topic", topic),
                    "suggested_tags": style_data.get("tags", "Pop, Melodic")
                }
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to parse style suggestions: {e}")
                return {
                    "lyrics": lyrics,
                    "suggested_topic": topic,
                    "suggested_tags": "Pop, Melodic"
                }

        except Exception as e:
            logger.error(f"Lyrics generation failed: {e}")
            raise e

    @staticmethod
    def generate_title(context: str, model: str = "llama3", provider_id: str = "") -> str:
        prompt = f"Generate a short, creative, 2-5 word song title based on this concept/lyrics: '{context}'. Return ONLY the title, no quotes or prefix."

        provider = LLMService._find_provider_for_model(model, provider_id)
        if not provider:
            return "Untitled Track"

        try:
            result = LLMService._call_llm(model, prompt, provider["id"])
            return result.strip().replace('"', '')
        except Exception as e:
            logger.error(f"LLM Auto-Title Exception: {e}")
            return "Untitled Track"

    @staticmethod
    def enhance_prompt(concept: str, model: str = "llama3", provider_id: str = "") -> dict:
        """Takes a simple user concept and returns a rich JSON with detailed topic and style tags."""
        prompt = (
            f"Act as a professional music producer. Transform this simple user concept into a detailed musical direction.\n"
            f"USER CONCEPT: '{concept}'\n\n"
            "INSTRUCTIONS:\n"
            "1. Create a 'topic' description that is evocative and detailed (1 sentence).\n"
            "2. Select 3-5 'tags' that describe the genre, mood, instruments, and tempo (comma separated).\n"
            "3. Return ONLY a raw JSON object with keys 'topic' and 'tags'. Do NOT wrap in markdown code blocks.\n\n"
            "Example Output:\n"
            '{"topic": "A melancholic acoustic ballad about lost love in autumn.", "tags": "Acoustic, Folk, Sad, Guitar, Slow"}'
        )

        provider = LLMService._find_provider_for_model(model, provider_id)
        if not provider:
            return {"topic": concept, "tags": "Pop, Experimental"}

        try:
            is_ollama = provider["type"] == "ollama"
            raw_response = LLMService._call_llm(model, prompt, provider["id"],
                                                 json_mode=is_ollama)
            raw_response = raw_response.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "").replace("```", "")

            try:
                return json.loads(raw_response)
            except json.JSONDecodeError:
                logger.warning(f"LLM failed JSON format: {raw_response}")
                return {"topic": concept, "tags": "Pop, Experimental"}
        except Exception as e:
            logger.error(f"Prompt enhancement failed: {e}")
            raise e

    @staticmethod
    def generate_inspiration(model: str = "llama3", provider_id: str = "") -> dict:
        """Generates a random, creative song concept and style."""
        prompt = (
            "Act as a professional music producer brainstorming new hit songs.\n"
            "INSTRUCTIONS:\n"
            "1. Invent a UNIQUE, creative song concept/topic (1 vivid sentence).\n"
            "2. Select a matching musical style (3-5 tags like genre, mood, instruments).\n"
            "3. Return ONLY a raw JSON object with keys 'topic' and 'tags'.\n\n"
            "Examples:\n"
            '{"topic": "A lonely astronaut drifting through the cosmos.", "tags": "Ambient, Space, Ethereal"}\n'
            '{"topic": "A cyberpunk detective chasing a suspect in rain.", "tags": "Synthwave, Dark, Retro"}'
        )

        provider = LLMService._find_provider_for_model(model, provider_id)
        if not provider:
            return {"topic": "A mysterious journey through time", "tags": "Orchestral, Epic, Cinematic"}

        try:
            is_ollama = provider["type"] == "ollama"
            raw_response = LLMService._call_llm(model, prompt, provider["id"],
                                                 json_mode=is_ollama, temperature=0.9)
            raw_response = raw_response.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "").replace("```", "")

            try:
                return json.loads(raw_response)
            except json.JSONDecodeError:
                logger.warning(f"LLM failed JSON format: {raw_response}")
                return {"topic": "A mysterious journey through time", "tags": "Orchestral, Epic, Cinematic"}
        except Exception as e:
            logger.error(f"Inspiration generation failed: {e}")
            raise e

    @staticmethod
    def generate_styles_list(model: str = "llama3") -> List[str]:
        """Returns 12 random styles from static library."""
        try:
            return random.sample(MUSIC_STYLES_LIBRARY, 12)
        except Exception as e:
            logger.error(f"Style generation failed: {e}")
            return MUSIC_STYLES_LIBRARY[:12]
