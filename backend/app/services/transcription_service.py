"""
HeartTranscriptor Service — Lyrics Transcription from Audio

Uses HeartMuLa/HeartTranscriptor-oss (Whisper-based) to extract lyrics from music files.
Optionally uses demucs for vocal separation before transcription for better accuracy.
"""

import asyncio
import gc
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import torch

logger = logging.getLogger(__name__)

# HuggingFace repo for HeartTranscriptor
HF_TRANSCRIPTOR_REPO = "HeartMuLa/HeartTranscriptor-oss"

# Check if heartlib's transcriptor pipeline is available
try:
    from heartlib.pipelines.lyrics_transcription import HeartTranscriptorPipeline
    TRANSCRIPTOR_AVAILABLE = True
except ImportError:
    TRANSCRIPTOR_AVAILABLE = False
    HeartTranscriptorPipeline = None

# Check if demucs (vocal separation) is available
try:
    import demucs
    DEMUCS_AVAILABLE = True
except ImportError:
    DEMUCS_AVAILABLE = False

# Model directory — same as music_service
_default_model_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models"
)
DEFAULT_MODEL_DIR = os.environ.get("HEARTMULA_MODEL_DIR", _default_model_dir)


class TranscriptionService:
    """Manages HeartTranscriptor model lifecycle and transcription requests."""

    def __init__(self):
        self.pipeline = None
        self.is_loading = False
        self.model_downloaded = False
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._dtype = torch.float16

    @property
    def is_ready(self) -> bool:
        return self.pipeline is not None

    def _get_model_path(self) -> Path:
        """Returns the path where HeartTranscriptor model should be stored."""
        return Path(DEFAULT_MODEL_DIR) / "HeartTranscriptor-oss"

    def check_model_exists(self) -> bool:
        """Check if HeartTranscriptor model files are downloaded."""
        model_path = self._get_model_path()
        if not model_path.exists():
            return False
        # Check for key Whisper files
        has_model = (model_path / "model.safetensors").exists() or any(
            model_path.glob("model-*.safetensors")
        )
        has_config = (model_path / "config.json").exists()
        return has_model and has_config

    async def download_model(self, progress_callback=None) -> bool:
        """Download HeartTranscriptor model from HuggingFace."""
        if self.check_model_exists():
            logger.info("HeartTranscriptor model already downloaded.")
            self.model_downloaded = True
            return True

        try:
            from huggingface_hub import snapshot_download

            model_path = self._get_model_path()
            model_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading HeartTranscriptor from {HF_TRANSCRIPTOR_REPO}...")
            if progress_callback:
                await progress_callback("Downloading HeartTranscriptor (~1.5GB)...")

            # Run download in thread to not block event loop
            hf_token = os.environ.get("HF_TOKEN")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: snapshot_download(
                    repo_id=HF_TRANSCRIPTOR_REPO,
                    local_dir=str(model_path),
                    token=hf_token,
                ),
            )

            self.model_downloaded = True
            logger.info("HeartTranscriptor model downloaded successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to download HeartTranscriptor: {e}")
            return False

    async def load_model(self) -> bool:
        """Load HeartTranscriptor pipeline into memory."""
        if self.pipeline is not None:
            return True

        if not TRANSCRIPTOR_AVAILABLE:
            logger.error("heartlib not installed — HeartTranscriptorPipeline unavailable")
            return False

        if not self.check_model_exists():
            logger.error("HeartTranscriptor model not downloaded yet")
            return False

        self.is_loading = True
        try:
            # The parent directory is what heartlib expects (it appends "HeartTranscriptor-oss")
            parent_path = str(Path(DEFAULT_MODEL_DIR))

            logger.info(f"Loading HeartTranscriptor from {parent_path}...")
            self.pipeline = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: HeartTranscriptorPipeline.from_pretrained(
                    pretrained_path=parent_path,
                    device="cpu",
                    dtype=self._dtype,
                ),
            )
            logger.info("HeartTranscriptor loaded successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to load HeartTranscriptor: {e}")
            self.pipeline = None
            return False
        finally:
            self.is_loading = False

    def unload_model(self):
        """Free HeartTranscriptor from GPU memory."""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("HeartTranscriptor unloaded from memory.")

    async def transcribe(
        self,
        audio_path: str,
        use_demucs: bool = False,
    ) -> dict:
        """
        Transcribe lyrics from an audio file.

        Args:
            audio_path: Path to the audio file (mp3, wav, flac, ogg)
            use_demucs: Whether to separate vocals first (better accuracy, slower)

        Returns:
            dict with 'text' (full transcription), 'chunks' (timed segments if available)
        """
        if not self.is_ready:
            # Try lazy loading
            loaded = await self.load_model()
            if not loaded:
                raise RuntimeError(
                    "HeartTranscriptor not loaded. Download the model first via /settings/transcriptor/download"
                )

        actual_path = audio_path

        # Optional: vocal separation with demucs
        if use_demucs and DEMUCS_AVAILABLE:
            actual_path = await self._separate_vocals(audio_path)

        try:
            # Run transcription in thread (Whisper is sync)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._run_transcription(actual_path),
            )
            return result

        finally:
            # Clean up temp vocal file if demucs was used
            if use_demucs and actual_path != audio_path and os.path.exists(actual_path):
                os.remove(actual_path)

    def _run_transcription(self, audio_path: str) -> dict:
        """Synchronous transcription call."""
        with torch.no_grad():
            result = self.pipeline(
                audio_path,
                max_new_tokens=256,
                num_beams=2,
                task="transcribe",
                condition_on_prev_tokens=False,
                compression_ratio_threshold=1.8,
                temperature=(0.0, 0.1, 0.2, 0.4),
                logprob_threshold=-1.0,
                no_speech_threshold=0.4,
                return_timestamps=True,
            )

        # result can be: {"text": "...", "chunks": [{"text": "...", "timestamp": (start, end)}]}
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        chunks = result.get("chunks", []) if isinstance(result, dict) else []

        return {
            "text": text.strip(),
            "chunks": chunks,
        }

    async def _separate_vocals(self, audio_path: str) -> str:
        """Use demucs to separate vocals from the music track."""
        if not DEMUCS_AVAILABLE:
            logger.warning("demucs not installed, skipping vocal separation")
            return audio_path

        try:
            temp_dir = tempfile.mkdtemp(prefix="heartmula_demucs_")

            # Run demucs as a subprocess for vocal separation
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "demucs",
                "--two-stems", "vocals",
                "-o", temp_dir,
                audio_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Find the vocals output
            # demucs output: temp_dir/htdemucs/trackname/vocals.wav
            vocals_dir = Path(temp_dir) / "htdemucs"
            if vocals_dir.exists():
                for track_dir in vocals_dir.iterdir():
                    vocals_path = track_dir / "vocals.wav"
                    if vocals_path.exists():
                        logger.info(f"Vocal separation complete: {vocals_path}")
                        return str(vocals_path)

            logger.warning("demucs did not produce vocals output, using original audio")
            return audio_path

        except Exception as e:
            logger.error(f"Vocal separation failed: {e}")
            return audio_path

    def get_status(self) -> dict:
        """Return current service status."""
        return {
            "available": TRANSCRIPTOR_AVAILABLE,
            "model_downloaded": self.check_model_exists(),
            "model_loaded": self.pipeline is not None,
            "is_loading": self.is_loading,
            "demucs_available": DEMUCS_AVAILABLE,
            "device": str(self._device),
        }


# Singleton instance
transcription_service = TranscriptionService()
