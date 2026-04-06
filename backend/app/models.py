from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from enum import Enum

# ============== Auth Models ==============

class UserStatus(str, Enum):
    PENDING = "pending"          # Waiting for admin approval
    APPROVED = "approved"        # Admin approved, waiting for user activation
    ACTIVE = "active"            # User activated account
    REJECTED = "rejected"        # Admin rejected
    SUSPENDED = "suspended"      # Account suspended


class CodeType(str, Enum):
    ADMIN_APPROVAL = "admin_approval"
    USER_ACTIVATION = "user_activation"
    LOGIN_CODE = "login_code"


class User(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    password_hash: Optional[str] = Field(default=None)
    is_admin: bool = Field(default=False)
    status: UserStatus = Field(default=UserStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None


class VerificationCode(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)
    code: str = Field(index=True)
    code_type: CodeType
    used: bool = Field(default=False)
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============== Music Models ==============

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    status: JobStatus = Field(default=JobStatus.QUEUED)
    title: Optional[str] = None
    prompt: str
    lyrics: Optional[str] = None
    tags: Optional[str] = None  # Added field for Style/Tags
    seed: Optional[int] = None # Added for Seed Consistency
    audio_path: Optional[str] = None
    duration_ms: int = 240000
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_msg: Optional[str] = None
    generation_time_seconds: Optional[float] = None  # Time taken to generate the track

class GenerationRequest(SQLModel):
    model_config = {"protected_namespaces": ()}
    prompt: str
    lyrics: Optional[str] = None
    duration_ms: int = 30000
    temperature: float = 1.0
    cfg_scale: float = 1.5
    topk: int = 50
    tags: Optional[str] = None
    seed: Optional[int] = None # Added for Seed Consistency
    llm_model: Optional[str] = None # specific LLM usage for title/lyrics
    title: Optional[str] = None # User-provided title (skips LLM title generation)
    parent_job_id: Optional[str] = None # For Track Extension (Phase 9)
    ref_audio_id: Optional[str] = None # Reference audio file ID for style conditioning
    style_influence: float = 100.0 # Style influence (0-100%, controls muq_segment_sec)
    ref_audio_start_sec: Optional[float] = None # Start time in seconds for reference audio segment (None = use middle)
    # Experimental: Advanced reference audio options
    negative_tags: Optional[str] = None # Negative prompt - styles to avoid (e.g. "noisy, distorted, low quality")
    ref_audio_as_noise: bool = False # Use reference audio as initial noise for generation
    ref_audio_noise_strength: float = 0.5 # Blend strength for ref audio noise (0.0-1.0)

class LyricsRequest(SQLModel):
    model_config = {"protected_namespaces": ()}
    topic: str
    model_name: str = "llama3"
    seed_lyrics: Optional[str] = None
    provider: str = "ollama"
    language: str = "English"
    duration_seconds: Optional[int] = None  # Target song duration for structure planning

class EnhancePromptRequest(SQLModel):
    model_config = {"protected_namespaces": ()}
    concept: str
    model_name: str = "llama3"
    provider: str = "ollama"

class InspirationRequest(SQLModel):
    model_config = {"protected_namespaces": ()}
    model_name: str = "llama3"
    provider: str = "ollama"


# Liked Songs (Favorites)
class LikedSong(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(index=True)
    liked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Playlists
class Playlist(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: Optional[str] = None
    cover_seed: Optional[str] = None  # For procedural cover generation
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Playlist Songs (Many-to-Many)
class PlaylistSong(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    playlist_id: UUID = Field(index=True)
    job_id: UUID = Field(index=True)
    position: int = 0  # Order in playlist
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Request/Response Models
class CreatePlaylistRequest(SQLModel):
    name: str
    description: Optional[str] = None


class UpdatePlaylistRequest(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddToPlaylistRequest(SQLModel):
    job_id: str


# ============== Settings Models ==============

class GPUInfo(SQLModel):
    index: int
    name: str
    vram_gb: float
    compute_capability: float
    supports_flash_attention: bool


class GPUStatusResponse(SQLModel):
    cuda_available: bool
    num_gpus: int
    gpus: list
    total_vram_gb: float


class GPUSettingsRequest(SQLModel):
    quantization_4bit: Optional[str] = None  # "auto", "true", "false" (for BitsAndBytes mode)
    sequential_offload: Optional[str] = None  # "auto", "true", "false"
    torch_compile: Optional[bool] = None
    torch_compile_mode: Optional[str] = None  # "default", "reduce-overhead", "max-autotune"
    mmgp_quantization: Optional[str] = None  # "true", "false" - mmgp runtime INT8 quantization


class GPUSettingsResponse(SQLModel):
    quantization_4bit: str
    sequential_offload: str
    torch_compile: bool
    torch_compile_mode: str
    mmgp_quantization: str = "false"  # mmgp runtime INT8 quantization


class StartupStatusResponse(SQLModel):
    status: str  # "not_started", "downloading", "loading", "ready", "error"
    progress: int
    message: str
    error: Optional[str] = None
    ready: bool


class ModelReloadResponse(SQLModel):
    status: str
    message: str


# ============== LLM Provider Models ==============

class LLMProviderModel(SQLModel):
    """A single model from a provider."""
    id: str
    name: str


class LLMProviderRequest(SQLModel):
    """Request to add/update a provider."""
    name: Optional[str] = None
    type: str = "openai"  # "openai" | "ollama"
    base_url: str = ""
    api_key: Optional[str] = None
    enabled: Optional[bool] = None


class LLMProviderResponse(SQLModel):
    """A provider with masked API key."""
    id: str
    name: str
    type: str
    base_url: str
    api_key: str  # masked
    enabled: bool
    models: list  # List[LLMProviderModel]
    enabled_models: list  # List[str]


class LLMToggleModelRequest(SQLModel):
    """Request to enable/disable a model."""
    model_id: str
    enabled: bool


class LLMActiveModel(SQLModel):
    """An active (enabled) model for the dropdown."""
    id: str
    name: str
    provider_id: str
    provider_name: str
    provider_type: str


# ============== Video Job Models ==============

class VideoJobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING_PROMPTS = "generating_prompts"
    GENERATING_CLIPS = "generating_clips"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoJob(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(index=True)  # FK -> Job (şarkı referansı)
    status: VideoJobStatus = Field(default=VideoJobStatus.QUEUED)
    mode: str = "auto"  # "auto" | "manual"
    custom_prompt: Optional[str] = None
    style_preset: str = "cinematic"  # cinematic, anime, realistic, abstract
    scene_prompts: Optional[str] = None  # JSON string — sahne listesi
    total_clips: int = 0
    completed_clips: int = 0
    video_path: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generation_time_seconds: Optional[float] = None


class VideoGenerateRequest(SQLModel):
    job_id: str  # Şarkı job ID
    mode: str = "auto"  # "auto" | "manual"
    custom_prompt: Optional[str] = None
    style_preset: str = "cinematic"


class VertexAISettingsRequest(SQLModel):
    service_account_json: Optional[str] = None  # JSON içerik (string)
    project_id: Optional[str] = None
    location: Optional[str] = "us-central1"
