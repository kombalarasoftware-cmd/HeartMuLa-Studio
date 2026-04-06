"""
Google GenAI Service — Gemini + Veo 3.1 entegrasyonu (google-genai SDK).

Gemini 2.5 Flash: Multimodal (audio + text) -> sahne prompt'lari
Veo 3.1: Text -> Video clip uretimi
"""
import json
import asyncio
import logging
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

STYLE_PRESETS = {
    "cinematic": "Cinematic film style, dramatic lighting, shallow depth of field, 24fps, widescreen, professional color grading",
    "anime": "Anime art style, vibrant colors, expressive characters, dynamic camera angles, Studio Ghibli inspired",
    "realistic": "Photorealistic, natural lighting, documentary style, high detail, 4K quality",
    "abstract": "Abstract visual art, flowing shapes, vivid colors, surreal imagery, artistic interpretation",
    "retro": "Retro 80s/90s aesthetic, neon colors, VHS grain, synthwave vibes, pixel art elements",
    "noir": "Film noir style, black and white with selective color, shadows, moody atmosphere, rain-soaked streets",
}

SCENE_GENERATION_PROMPT = """You are a professional music video director. Analyze this song and create a scene-by-scene video script.

SONG INFORMATION:
- Title: {title}
- Style/Genre: {tags}
- Duration: {duration_sec} seconds
- Lyrics:
{lyrics}

INSTRUCTIONS:
1. Divide the song into {num_scenes} scenes of approximately {clip_duration} seconds each
2. For each scene, write a detailed video generation prompt
3. Maintain visual consistency across all scenes (same characters, color palette, setting)
4. Match the visual mood to the music's energy and lyrics meaning
5. Include camera movements, lighting, and atmosphere details

STYLE DIRECTIVE: {style_directive}

CONSISTENCY RULES:
- Define main character(s) appearance in scene 1, reference the same description in subsequent scenes
- Use a consistent color palette throughout
- Maintain the same visual style (lighting, grain, contrast)

OUTPUT FORMAT (JSON array):
[
  {{
    "scene_index": 0,
    "start_sec": 0,
    "end_sec": {clip_duration},
    "prompt": "Detailed visual description for video generation...",
    "mood": "energetic/calm/melancholic/etc"
  }},
  ...
]

Return ONLY the JSON array, no other text."""

MANUAL_SCENE_PROMPT = """You are a professional music video director. Create {num_scenes} scene prompts based on the user's creative direction.

USER'S VISION: {custom_prompt}

SONG INFO:
- Duration: {duration_sec} seconds
- Style: {tags}
- Lyrics: {lyrics}

STYLE: {style_directive}

Create {num_scenes} scenes of ~{clip_duration} seconds each. Maintain visual consistency.

OUTPUT FORMAT (JSON array):
[
  {{
    "scene_index": 0,
    "start_sec": 0,
    "end_sec": {clip_duration},
    "prompt": "Detailed visual description...",
    "mood": "energetic/calm/etc"
  }},
  ...
]

Return ONLY the JSON array."""


class VertexAIService:
    """Google GenAI service — Gemini + Veo entegrasyonu."""

    _instance = None
    _configured = False
    _project_id: Optional[str] = None
    _location: str = "us-central1"
    _credentials_json: Optional[str] = None
    _client = None  # google.genai.Client

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def configure(self, service_account_json: str, project_id: str, location: str = "us-central1"):
        """Google GenAI client'i yapılandir."""
        try:
            from google import genai
            from google.oauth2 import service_account

            creds_dict = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # google-genai Client — Vertex AI backend
            self._client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location,
                credentials=credentials,
            )

            self._project_id = project_id
            self._location = location
            self._credentials_json = service_account_json
            self._configured = True
            logger.info(f"[GenAI] Configured: project={project_id}, location={location}")
        except Exception as e:
            self._configured = False
            logger.error(f"[GenAI] Configuration failed: {e}")
            raise ValueError(f"Invalid configuration: {e}")

    def is_configured(self) -> bool:
        return self._configured

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": self._configured,
            "project_id": self._project_id,
            "location": self._location,
        }

    def get_settings_for_save(self) -> Dict[str, Any]:
        """Settings'e kaydedilecek veriyi dondur."""
        if not self._configured:
            return {}
        return {
            "service_account_json": self._credentials_json,
            "project_id": self._project_id,
            "location": self._location,
        }

    async def generate_scene_prompts(
        self,
        audio_path: str,
        title: str,
        lyrics: str,
        tags: str,
        duration_ms: int,
        mode: str = "auto",
        custom_prompt: Optional[str] = None,
        style_preset: str = "cinematic",
        clip_duration: int = 8,
    ) -> List[Dict[str, Any]]:
        """Gemini ile sahne prompt'lari uret."""
        if not self._configured or not self._client:
            raise ValueError("Google GenAI not configured")

        from google.genai import types

        duration_sec = duration_ms / 1000
        num_scenes = max(1, int(duration_sec / clip_duration))
        style_directive = STYLE_PRESETS.get(style_preset, STYLE_PRESETS["cinematic"])

        # Prompt sec
        if mode == "manual" and custom_prompt:
            prompt_template = MANUAL_SCENE_PROMPT.format(
                custom_prompt=custom_prompt,
                duration_sec=int(duration_sec),
                tags=tags or "pop",
                lyrics=lyrics or "(instrumental)",
                style_directive=style_directive,
                num_scenes=num_scenes,
                clip_duration=clip_duration,
            )
        else:
            prompt_template = SCENE_GENERATION_PROMPT.format(
                title=title or "Untitled",
                tags=tags or "pop",
                duration_sec=int(duration_sec),
                lyrics=lyrics or "(instrumental)",
                style_directive=style_directive,
                num_scenes=num_scenes,
                clip_duration=clip_duration,
            )

        contents = []

        # Audio dosyasini ekle (Gemini multimodal)
        audio_file = Path(audio_path)
        if audio_file.exists() and audio_file.stat().st_size < 20 * 1024 * 1024:
            audio_bytes = audio_file.read_bytes()
            # Determine mime type
            suffix = audio_file.suffix.lower()
            mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac", ".ogg": "audio/ogg"}
            mime_type = mime_map.get(suffix, "audio/mpeg")
            contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime_type))
            contents.append("Listen to this song carefully. Analyze its rhythm, energy changes, mood transitions, and tempo.")

        contents.append(prompt_template)

        logger.info(f"[GenAI] Generating {num_scenes} scene prompts with Gemini...")

        # Gemini 2.5 Flash — en guncel ve hizli model
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
            )
        )

        # JSON parse
        text = response.text.strip()
        # Markdown code block temizligi
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        scenes = json.loads(text)
        logger.info(f"[GenAI] Generated {len(scenes)} scene prompts")
        return scenes

    async def generate_video_clip(
        self,
        prompt: str,
        style_prefix: str = "",
        duration_sec: int = 8,
        aspect_ratio: str = "16:9",
    ) -> bytes:
        """Veo 3.1 ile tek bir video clip uret."""
        if not self._configured or not self._client:
            raise ValueError("Google GenAI not configured")

        full_prompt = f"{style_prefix}. {prompt}" if style_prefix else prompt

        logger.info(f"[Veo] Generating clip: {full_prompt[:80]}...")

        # google-genai SDK ile Veo 3.1 video uretimi
        operation = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._client.models.generate_videos(
                model="veo-3.0-generate-001",
                prompt=full_prompt,
                config={
                    "aspect_ratio": aspect_ratio,
                    "number_of_videos": 1,
                    "duration_seconds": duration_sec,
                    "person_generation": "allow_all",
                },
            )
        )

        # Polling — operation tamamlanana kadar bekle
        max_wait = 600  # 10 dakika max
        poll_interval = 10
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.operations.get(operation)
            )

            if result.done:
                if result.error:
                    raise ValueError(f"Veo generation failed: {result.error}")

                # Video verisini al
                if hasattr(result, 'response') and result.response:
                    generated_videos = result.response.generated_videos
                    if generated_videos and len(generated_videos) > 0:
                        video = generated_videos[0].video
                        if hasattr(video, 'video_bytes') and video.video_bytes:
                            logger.info(f"[Veo] Clip generated ({len(video.video_bytes)} bytes)")
                            return video.video_bytes
                        elif hasattr(video, 'uri') and video.uri:
                            # GCS'den indir
                            return await self._download_from_gcs(video.uri)

                raise ValueError("No video data in response")

            logger.info(f"[Veo] Waiting... ({elapsed}s)")

        raise TimeoutError(f"Video generation timed out after {max_wait}s")

    async def _download_from_gcs(self, gcs_uri: str) -> bytes:
        """GCS URI'den video dosyasini indir."""
        import aiohttp
        from google.auth.transport.requests import Request as AuthRequest
        from google.oauth2 import service_account

        creds_dict = json.loads(self._credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(AuthRequest())

        if gcs_uri.startswith("gs://"):
            # gs://bucket/path -> API URL
            parts = gcs_uri[5:].split("/", 1)
            bucket = parts[0]
            obj_path = parts[1] if len(parts) > 1 else ""
            import urllib.parse
            url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{urllib.parse.quote(obj_path, safe='')}?alt=media"
        else:
            url = gcs_uri

        headers = {"Authorization": f"Bearer {credentials.token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to download from GCS: {resp.status}")
                return await resp.read()


# Singleton instance
vertex_ai_service = VertexAIService()
