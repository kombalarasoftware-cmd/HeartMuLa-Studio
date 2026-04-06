import asyncio
import os
import uuid as uuid_module
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load .env file
load_dotenv("backend/.env")
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Session, create_engine, select
from typing import List
from datetime import datetime, timezone
from uuid import UUID

from backend.app.models import (
    Job, JobStatus, GenerationRequest, LyricsRequest, EnhancePromptRequest, InspirationRequest,
    LikedSong, Playlist, PlaylistSong, CreatePlaylistRequest, UpdatePlaylistRequest, AddToPlaylistRequest,
    GPUSettingsRequest, GPUSettingsResponse, GPUStatusResponse, StartupStatusResponse, ModelReloadResponse,
    LLMProviderRequest, LLMProviderResponse, LLMToggleModelRequest, LLMActiveModel,
    VideoJob, VideoJobStatus, VideoGenerateRequest, VertexAISettingsRequest
)
from backend.app.services.music_service import music_service
from backend.app.services.llm_service import LLMService
from backend.app.services.transcription_service import transcription_service
from backend.app.services.video_service import video_service
from backend.app.services.vertex_ai_service import vertex_ai_service
from backend.app.services.auth_service import auth_service, verify_jwt, seed_super_admin
from backend.app.models import User

# Database - configurable path for Docker support
sqlite_file_name = os.environ.get("HEARTMULA_DB_PATH", "backend/jobs.db")
# Ensure directory exists for Docker volume mount
os.makedirs(os.path.dirname(sqlite_file_name) if os.path.dirname(sqlite_file_name) else ".", exist_ok=True)
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def run_migrations():
    """Run simple database migrations for new columns."""
    from sqlalchemy import text
    with engine.connect() as conn:
        # Add generation_time_seconds column if it doesn't exist
        try:
            conn.execute(text("ALTER TABLE job ADD COLUMN generation_time_seconds REAL"))
            conn.commit()
            print("[Migration] Added generation_time_seconds column to job table")
        except Exception:
            pass  # Column already exists

        # Add password_hash column to user table
        try:
            conn.execute(text("ALTER TABLE user ADD COLUMN password_hash TEXT"))
            conn.commit()
            print("[Migration] Added password_hash column to user table")
        except Exception:
            pass

        # Add is_admin column to user table
        try:
            conn.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
            conn.commit()
            print("[Migration] Added is_admin column to user table")
        except Exception:
            pass

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    run_migrations()
    # Seed super admin user
    with Session(engine) as session:
        seed_super_admin(session)
    # Initialize Vertex AI from saved settings
    saved_vertex = music_service.current_settings.get("vertex_ai", {})
    if saved_vertex and saved_vertex.get("service_account_json"):
        try:
            vertex_ai_service.configure(
                service_account_json=saved_vertex["service_account_json"],
                project_id=saved_vertex.get("project_id", ""),
                location=saved_vertex.get("location", "us-central1"),
            )
        except Exception as e:
            print(f"[Startup] Vertex AI init failed: {e}")
    # Start model initialization in background - server starts immediately
    # Frontend can connect and show progress via SSE
    asyncio.create_task(music_service.initialize_with_progress())
    yield
    # Shutdown Event Manager (Closes SSE connections)
    event_manager.shutdown()
    music_service.shutdown_all()

app = FastAPI(lifespan=lifespan, title="HeartMuLa Music API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files (Audio Serving)
app.mount("/audio", StaticFiles(directory="backend/generated_audio"), name="audio")

# Reference Audio Storage
REF_AUDIO_DIR = "backend/ref_audio"
os.makedirs(REF_AUDIO_DIR, exist_ok=True)

# Video Output Storage
VIDEO_OUTPUT_DIR = "backend/generated_videos"
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
app.mount("/video", StaticFiles(directory=VIDEO_OUTPUT_DIR), name="video")
app.mount("/ref_audio", StaticFiles(directory=REF_AUDIO_DIR), name="ref_audio")

# --- Auth Dependency ---

from fastapi import Header

def get_current_user_optional(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        return None
    return verify_jwt(authorization[7:])


def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_jwt(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# --- Auth Routes ---

class RegisterRequest(SQLModel):
    name: str
    email: str

class SendCodeRequest(SQLModel):
    email: str

class VerifyCodeRequest(SQLModel):
    email: str
    code: str

class PasswordLoginRequest(SQLModel):
    email: str
    password: str


@app.post("/auth/login")
def auth_login_password(req: PasswordLoginRequest):
    with Session(engine) as session:
        result = auth_service.login_with_password(session, req.email, req.password)
        if "error" in result:
            raise HTTPException(status_code=401, detail=result["message"])
        return result


@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    with Session(engine) as session:
        result = auth_service.register_user(session, req.name, req.email)
        if "error" in result:
            status_code = 409 if result["error"] == "email_exists" else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result


@app.post("/auth/send-code")
def auth_send_code(req: SendCodeRequest):
    with Session(engine) as session:
        result = auth_service.send_login_code(session, req.email)
        if "error" in result:
            code_map = {"not_found": 404, "pending": 403, "not_activated": 403, "rejected": 403}
            raise HTTPException(status_code=code_map.get(result["error"], 400), detail=result["message"])
        return result


@app.post("/auth/verify")
def auth_verify(req: VerifyCodeRequest):
    with Session(engine) as session:
        result = auth_service.verify_login_code(session, req.email, req.code)
        if "error" in result:
            raise HTTPException(status_code=401, detail=result["message"])
        return result


@app.get("/auth/approve")
def auth_approve(token: str):
    with Session(engine) as session:
        result = auth_service.approve_user(session, token)
        from fastapi.responses import HTMLResponse
        if "error" in result:
            return HTMLResponse(content=f'<html><body style="background:#1a1a2e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#ef4444">Error</h1><p>{result["message"]}</p></div></body></html>')
        return HTMLResponse(content=f'<html><body style="background:#1a1a2e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#22c55e">Approved!</h1><p>{result["message"]}</p></div></body></html>')


@app.get("/auth/reject")
def auth_reject(token: str):
    with Session(engine) as session:
        result = auth_service.reject_user(session, token)
        from fastapi.responses import HTMLResponse
        if "error" in result:
            return HTMLResponse(content=f'<html><body style="background:#1a1a2e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#ef4444">Error</h1><p>{result["message"]}</p></div></body></html>')
        return HTMLResponse(content=f'<html><body style="background:#1a1a2e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#f59e0b">Rejected</h1><p>{result["message"]}</p></div></body></html>')


@app.get("/auth/activate")
def auth_activate(token: str):
    from backend.app.services.auth_service import APP_URL as _APP_URL
    with Session(engine) as session:
        result = auth_service.activate_user(session, token)
        from fastapi.responses import HTMLResponse
        if "error" in result:
            return HTMLResponse(content=f'<html><body style="background:#1a1a2e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#ef4444">Error</h1><p>{result["message"]}</p></div></body></html>')
        return HTMLResponse(content=f'<html><body style="background:#1a1a2e;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#22c55e">Account Activated!</h1><p>{result["message"]}</p><a href="{_APP_URL}" style="display:inline-block;background:#22c55e;color:#000;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:20px">Go to HeartMuLa Studio</a></div></body></html>')


@app.get("/auth/me")
def auth_me(user=Depends(get_current_user)):
    with Session(engine) as session:
        db_user = session.exec(select(User).where(User.id == UUID(user["sub"]))).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": str(db_user.id), "name": db_user.name, "email": db_user.email, "status": db_user.status, "is_admin": db_user.is_admin}


# --- Routes ---

@app.post("/upload/ref_audio")
async def upload_ref_audio(file: UploadFile = File(...)):
    """Upload a reference audio file for style conditioning."""
    # Validate file type
    allowed_types = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/flac", "audio/ogg"]
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}. Allowed: mp3, wav, flac, ogg")

    # Generate unique ID for the file
    file_id = str(uuid_module.uuid4())

    # Get file extension
    original_name = file.filename or "audio.mp3"
    ext = os.path.splitext(original_name)[1] or ".mp3"

    # Save file
    file_path = os.path.join(REF_AUDIO_DIR, f"{file_id}{ext}")
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    return {
        "id": file_id,
        "filename": original_name,
        "path": f"/ref_audio/{file_id}{ext}",
        "size": len(contents)
    }


@app.delete("/upload/ref_audio/{file_id}")
async def delete_ref_audio(file_id: str):
    """Delete a previously uploaded reference audio file."""
    # Find and delete the file (could have various extensions)
    for ext in [".mp3", ".wav", ".flac", ".ogg"]:
        file_path = os.path.join(REF_AUDIO_DIR, f"{file_id}{ext}")
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"status": "deleted", "id": file_id}

    raise HTTPException(status_code=404, detail="Reference audio not found")

@app.get("/health")
def health_check():
    return {"status": "ok", "model_loaded": music_service.pipeline is not None}

@app.get("/models/lyrics")
def get_lyrics_models():
    """Get all active (enabled) models across all providers."""
    return {"models": LLMService.get_active_models()}

@app.get("/languages")
def get_languages():
    return {"languages": LLMService.get_supported_languages()}

@app.post("/generate/enhance_prompt")
def enhance_prompt(req: EnhancePromptRequest):
    try:
        result = LLMService.enhance_prompt(req.concept, req.model_name, req.provider)
        return result
    except Exception as e:
        return {"topic": req.concept, "tags": "Pop"}

@app.post("/generate/evaluate_inspiration")
def generate_inspiration(req: InspirationRequest):
    try:
        result = LLMService.generate_inspiration(req.model_name, req.provider)
        return result
    except Exception as e:
        return {"topic": "A futuristic city in the clouds", "tags": "Electronic, ambient, sci-fi"}

@app.post("/generate/styles")
def generate_styles(req: InspirationRequest):
    try:
        styles = LLMService.generate_styles_list(req.model_name)
        return {"styles": styles}
    except Exception:
        return {"styles": ["Pop", "Rock", "Jazz"]}

@app.post("/generate/lyrics")
def generate_lyrics(req: LyricsRequest):
    try:
        result = LLMService.generate_lyrics(req.topic, req.model_name, req.seed_lyrics, req.provider, req.language, req.duration_seconds)
        return {
            "lyrics": result["lyrics"],
            "suggested_topic": result.get("suggested_topic", req.topic),
            "suggested_tags": result.get("suggested_tags", "Pop, Melodic")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/music")
async def generate_music(req: GenerationRequest, background_tasks: BackgroundTasks):
    # Create Job Record
    seed_val = req.seed
    if seed_val is None:
         import random
         seed_val = random.randint(0, 2**32 - 1)
         
    job = Job(prompt=req.prompt, lyrics=req.lyrics, duration_ms=req.duration_ms, tags=req.tags, seed=seed_val)
    with Session(engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)
    
    # Enqueue Background Task
    background_tasks.add_task(music_service.generate_task, job.id, req, engine)
    
    return {"job_id": job.id, "status": job.status}

@app.get("/jobs/{job_id}", response_model=Job)
def get_job_status(job_id: UUID):
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

@app.get("/history", response_model=List[Job])
def get_history():
    with Session(engine) as session:
        jobs = session.exec(select(Job).order_by(Job.created_at.desc())).all()
        return jobs

@app.patch("/jobs/{job_id}", response_model=Job)
def rename_job(job_id: UUID, upgrade: dict):
    # Minimal schema for update, expecting {"title": "new name"}
    new_title = upgrade.get("title")
    if not new_title:
        raise HTTPException(status_code=400, detail="Title is required")
        
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job.title = new_title
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

@app.get("/download_track/{job_id}")
def download_track(job_id: UUID):
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job or not job.audio_path:
            raise HTTPException(status_code=404, detail="Track not found")
            
        # audio_path is "/audio/filename.mp3" -> "backend/generated_audio/filename.mp3"
        filename = job.audio_path.replace("/audio/", "")
        file_path = f"backend/generated_audio/{filename}"
        
        # Sanitize Title for Filename
        import re
        safe_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', job.title or "untitled")
        safe_title = safe_title.strip().replace(" ", "_")
        download_name = f"{safe_title}.mp3"
        
        return FileResponse(file_path, media_type="audio/mpeg", filename=download_name)

@app.delete("/jobs/{job_id}")
def delete_job(job_id: UUID):
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Delete audio file if exists
        if job.audio_path:
            # audio_path is like "/audio/filename.mp3"
            # We need to map it back to "backend/generated_audio/filename.mp3"
            filename = job.audio_path.replace("/audio/", "")
            file_path = f"backend/generated_audio/{filename}"
            import os
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
        
        session.delete(job)
        session.commit()
        return {"status": "deleted", "id": job_id}

@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: UUID):
    # Try to cancel running task via service
    if music_service.cancel_job(str(job_id)):
        return {"status": "cancelling", "id": job_id}
    
    # If not running, maybe update status in DB directly?
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job and job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
            job.status = JobStatus.FAILED
            job.error_msg = "Cancelled by user"
            session.add(job)
            session.commit()
            return {"status": "cancelled", "id": job_id}
            
    raise HTTPException(status_code=400, detail="Job not active or already completed")

# ============== TRANSCRIPTION (HeartTranscriptor) ==============

@app.get("/transcriptor/status")
def get_transcriptor_status():
    """Get HeartTranscriptor service status."""
    return transcription_service.get_status()


@app.post("/transcriptor/download")
async def download_transcriptor(background_tasks: BackgroundTasks):
    """Download HeartTranscriptor model from HuggingFace."""
    if transcription_service.is_loading:
        raise HTTPException(status_code=409, detail="Model is already being downloaded/loaded")

    if transcription_service.check_model_exists():
        return {"status": "already_downloaded", "message": "HeartTranscriptor model already exists"}

    background_tasks.add_task(transcription_service.download_model)
    return {"status": "downloading", "message": "HeartTranscriptor download started (~1.5GB)"}


@app.post("/transcriptor/load")
async def load_transcriptor():
    """Load HeartTranscriptor model into GPU memory."""
    if transcription_service.is_loading:
        raise HTTPException(status_code=409, detail="Model is already loading")

    if transcription_service.is_ready:
        return {"status": "already_loaded", "message": "HeartTranscriptor is already loaded"}

    if not transcription_service.check_model_exists():
        raise HTTPException(status_code=404, detail="Model not downloaded. Call /transcriptor/download first")

    success = await transcription_service.load_model()
    if success:
        return {"status": "loaded", "message": "HeartTranscriptor loaded successfully"}
    raise HTTPException(status_code=500, detail="Failed to load HeartTranscriptor")


@app.post("/transcriptor/unload")
def unload_transcriptor():
    """Unload HeartTranscriptor from GPU memory to free VRAM."""
    transcription_service.unload_model()
    return {"status": "unloaded", "message": "HeartTranscriptor unloaded from GPU memory"}


@app.post("/transcriptor/transcribe")
async def transcribe_audio(file: UploadFile = File(...), use_demucs: bool = False):
    """
    Transcribe lyrics from an uploaded audio file.

    - **file**: Audio file (mp3, wav, flac, ogg)
    - **use_demucs**: Set to true for vocal separation before transcription (better accuracy, slower)
    """
    # Validate file type
    allowed_types = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/flac", "audio/ogg"]
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}. Allowed: mp3, wav, flac, ogg")

    # Save uploaded file to temp location
    import tempfile
    ext = os.path.splitext(file.filename or "audio.mp3")[1] or ".mp3"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix="heartmula_transcribe_")
    try:
        contents = await file.read()
        tmp.write(contents)
        tmp.close()

        # Transcribe
        result = await transcription_service.transcribe(tmp.name, use_demucs=use_demucs)
        return result

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(tmp.name):
            os.remove(tmp.name)


@app.post("/transcriptor/transcribe/{job_id}")
async def transcribe_job_audio(job_id: UUID, use_demucs: bool = False):
    """Transcribe lyrics from an existing generated track by job ID."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job or not job.audio_path:
            raise HTTPException(status_code=404, detail="Track not found")

    # Resolve audio file path
    filename = job.audio_path.replace("/audio/", "")
    file_path = f"backend/generated_audio/{filename}"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    try:
        result = await transcription_service.transcribe(file_path, use_demucs=use_demucs)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


from fastapi.responses import StreamingResponse
from backend.app.services.music_service import event_manager

@app.get("/events")
async def events():
    async def event_generator():
        q = event_manager.subscribe()
        try:
            while True:
                # Wait for new event using asyncio.wait_for to allow checking client disconnected
                # actually Queue.get is async so it yields control
                try:
                    data = await asyncio.wait_for(q.get(), timeout=1.0)
                    if "event: shutdown" in data:
                        break
                    yield data
                except asyncio.TimeoutError:
                    # Wake up loop to check for cancellation or keep-alive
                    # yield ": keep-alive\n\n" # Optional: send comment to keep client connection alive
                    continue
        except asyncio.CancelledError:
             # Server shutting down
             pass
        except Exception:
            pass
        finally:
            event_manager.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============== LIKES (Favorites) ==============

@app.post("/songs/{job_id}/like")
def like_song(job_id: UUID):
    with Session(engine) as session:
        # Check if job exists
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Song not found")

        # Check if already liked
        existing = session.exec(select(LikedSong).where(LikedSong.job_id == job_id)).first()
        if existing:
            return {"status": "already_liked", "job_id": str(job_id)}

        # Add like
        liked = LikedSong(job_id=job_id)
        session.add(liked)
        session.commit()
        return {"status": "liked", "job_id": str(job_id)}


@app.delete("/songs/{job_id}/like")
def unlike_song(job_id: UUID):
    with Session(engine) as session:
        liked = session.exec(select(LikedSong).where(LikedSong.job_id == job_id)).first()
        if not liked:
            raise HTTPException(status_code=404, detail="Song not in favorites")

        session.delete(liked)
        session.commit()
        return {"status": "unliked", "job_id": str(job_id)}


@app.get("/songs/liked")
def get_liked_songs():
    with Session(engine) as session:
        # Get all liked song IDs
        liked_entries = session.exec(select(LikedSong).order_by(LikedSong.liked_at.desc())).all()
        liked_job_ids = [entry.job_id for entry in liked_entries]

        # Get the actual job details
        if not liked_job_ids:
            return {"songs": [], "liked_ids": []}

        jobs = session.exec(select(Job).where(Job.id.in_(liked_job_ids))).all()
        # Sort by liked order
        job_map = {job.id: job for job in jobs}
        sorted_jobs = [job_map[jid] for jid in liked_job_ids if jid in job_map]

        return {"songs": sorted_jobs, "liked_ids": [str(jid) for jid in liked_job_ids]}


@app.get("/songs/liked/ids")
def get_liked_song_ids():
    """Quick endpoint to get just the IDs of liked songs"""
    with Session(engine) as session:
        liked_entries = session.exec(select(LikedSong)).all()
        return {"liked_ids": [str(entry.job_id) for entry in liked_entries]}


# ============== PLAYLISTS ==============

@app.get("/playlists")
def get_playlists():
    with Session(engine) as session:
        playlists = session.exec(select(Playlist).order_by(Playlist.updated_at.desc())).all()

        # Get song count for each playlist
        result = []
        for playlist in playlists:
            song_count = len(session.exec(select(PlaylistSong).where(PlaylistSong.playlist_id == playlist.id)).all())
            result.append({
                "id": str(playlist.id),
                "name": playlist.name,
                "description": playlist.description,
                "cover_seed": playlist.cover_seed,
                "song_count": song_count,
                "created_at": playlist.created_at.isoformat(),
                "updated_at": playlist.updated_at.isoformat()
            })

        return {"playlists": result}


@app.post("/playlists")
def create_playlist(req: CreatePlaylistRequest):
    with Session(engine) as session:
        import uuid
        playlist = Playlist(
            name=req.name,
            description=req.description,
            cover_seed=str(uuid.uuid4())  # Random seed for procedural cover
        )
        session.add(playlist)
        session.commit()
        session.refresh(playlist)

        return {
            "id": str(playlist.id),
            "name": playlist.name,
            "description": playlist.description,
            "cover_seed": playlist.cover_seed,
            "created_at": playlist.created_at.isoformat()
        }


@app.get("/playlists/{playlist_id}")
def get_playlist(playlist_id: UUID):
    with Session(engine) as session:
        playlist = session.get(Playlist, playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get songs in playlist with order
        playlist_songs = session.exec(
            select(PlaylistSong)
            .where(PlaylistSong.playlist_id == playlist_id)
            .order_by(PlaylistSong.position)
        ).all()

        # Get job details for each song
        job_ids = [ps.job_id for ps in playlist_songs]
        jobs = session.exec(select(Job).where(Job.id.in_(job_ids))).all() if job_ids else []
        job_map = {job.id: job for job in jobs}

        songs = []
        for ps in playlist_songs:
            if ps.job_id in job_map:
                job = job_map[ps.job_id]
                songs.append({
                    "job": job,
                    "position": ps.position,
                    "added_at": ps.added_at.isoformat()
                })

        return {
            "id": str(playlist.id),
            "name": playlist.name,
            "description": playlist.description,
            "cover_seed": playlist.cover_seed,
            "songs": songs,
            "song_count": len(songs),
            "created_at": playlist.created_at.isoformat(),
            "updated_at": playlist.updated_at.isoformat()
        }


@app.patch("/playlists/{playlist_id}")
def update_playlist(playlist_id: UUID, req: UpdatePlaylistRequest):
    with Session(engine) as session:
        playlist = session.get(Playlist, playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        if req.name is not None:
            playlist.name = req.name
        if req.description is not None:
            playlist.description = req.description
        playlist.updated_at = datetime.now(timezone.utc)

        session.add(playlist)
        session.commit()
        session.refresh(playlist)

        return {
            "id": str(playlist.id),
            "name": playlist.name,
            "description": playlist.description,
            "updated_at": playlist.updated_at.isoformat()
        }


@app.delete("/playlists/{playlist_id}")
def delete_playlist(playlist_id: UUID):
    with Session(engine) as session:
        playlist = session.get(Playlist, playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Delete all playlist songs
        playlist_songs = session.exec(select(PlaylistSong).where(PlaylistSong.playlist_id == playlist_id)).all()
        for ps in playlist_songs:
            session.delete(ps)

        session.delete(playlist)
        session.commit()

        return {"status": "deleted", "id": str(playlist_id)}


@app.post("/playlists/{playlist_id}/songs")
def add_song_to_playlist(playlist_id: UUID, req: AddToPlaylistRequest):
    with Session(engine) as session:
        # Verify playlist exists
        playlist = session.get(Playlist, playlist_id)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        job_id = UUID(req.job_id)

        # Verify song exists
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Song not found")

        # Check if already in playlist
        existing = session.exec(
            select(PlaylistSong)
            .where(PlaylistSong.playlist_id == playlist_id)
            .where(PlaylistSong.job_id == job_id)
        ).first()

        if existing:
            return {"status": "already_in_playlist", "playlist_id": str(playlist_id), "job_id": req.job_id}

        # Get next position
        max_pos = session.exec(
            select(PlaylistSong.position)
            .where(PlaylistSong.playlist_id == playlist_id)
            .order_by(PlaylistSong.position.desc())
        ).first()
        next_pos = (max_pos or 0) + 1

        # Add to playlist
        playlist_song = PlaylistSong(playlist_id=playlist_id, job_id=job_id, position=next_pos)
        session.add(playlist_song)

        # Update playlist timestamp
        playlist.updated_at = datetime.now(timezone.utc)
        session.add(playlist)

        session.commit()

        return {"status": "added", "playlist_id": str(playlist_id), "job_id": req.job_id, "position": next_pos}


@app.delete("/playlists/{playlist_id}/songs/{job_id}")
def remove_song_from_playlist(playlist_id: UUID, job_id: UUID):
    with Session(engine) as session:
        playlist_song = session.exec(
            select(PlaylistSong)
            .where(PlaylistSong.playlist_id == playlist_id)
            .where(PlaylistSong.job_id == job_id)
        ).first()

        if not playlist_song:
            raise HTTPException(status_code=404, detail="Song not in playlist")

        session.delete(playlist_song)

        # Update playlist timestamp
        playlist = session.get(Playlist, playlist_id)
        if playlist:
            playlist.updated_at = datetime.now(timezone.utc)
            session.add(playlist)

        session.commit()

        return {"status": "removed", "playlist_id": str(playlist_id), "job_id": str(job_id)}


# ============== SETTINGS & STARTUP STATUS ==============

@app.get("/settings/startup/status", response_model=StartupStatusResponse)
def get_startup_status():
    """Get current startup/initialization status."""
    return music_service.get_startup_status()


@app.get("/settings/gpu/status", response_model=GPUStatusResponse)
def get_gpu_status():
    """Get GPU hardware information."""
    return music_service.get_gpu_info()


@app.get("/settings/gpu", response_model=GPUSettingsResponse)
def get_gpu_settings():
    """Get current GPU settings."""
    return music_service.current_settings


@app.put("/settings/gpu", response_model=GPUSettingsResponse)
def update_gpu_settings(settings: GPUSettingsRequest):
    """Update GPU settings (does not reload models)."""
    if settings.quantization_4bit is not None:
        music_service.current_settings["quantization_4bit"] = settings.quantization_4bit
    if settings.sequential_offload is not None:
        music_service.current_settings["sequential_offload"] = settings.sequential_offload
    if settings.torch_compile is not None:
        music_service.current_settings["torch_compile"] = settings.torch_compile
    if settings.torch_compile_mode is not None:
        music_service.current_settings["torch_compile_mode"] = settings.torch_compile_mode
    # Persist settings to disk
    music_service._save_settings()
    return music_service.current_settings


@app.post("/settings/gpu/reload", response_model=ModelReloadResponse)
async def reload_models(settings: GPUSettingsRequest, background_tasks: BackgroundTasks):
    """Reload models with new settings."""
    # Check if models are currently loading
    if music_service.is_loading:
        raise HTTPException(status_code=409, detail="Models are currently loading")

    # Check if a job is processing
    if len(music_service.active_jobs) > 0:
        raise HTTPException(status_code=409, detail="Cannot reload while a job is processing")

    if len(music_service.job_queue) > 0:
        raise HTTPException(status_code=409, detail="Cannot reload while jobs are queued")

    # Convert settings to dict
    new_settings = {}
    if settings.quantization_4bit is not None:
        new_settings["quantization_4bit"] = settings.quantization_4bit
    if settings.sequential_offload is not None:
        new_settings["sequential_offload"] = settings.sequential_offload
    if settings.torch_compile is not None:
        new_settings["torch_compile"] = settings.torch_compile
    if settings.torch_compile_mode is not None:
        new_settings["torch_compile_mode"] = settings.torch_compile_mode

    # Start reload in background
    background_tasks.add_task(music_service.reload_models, new_settings)

    return {"status": "reloading", "message": "Model reload started"}


# ============== LLM SETTINGS ==============

# ============== LLM PROVIDERS (Multi-Provider) ==============

@app.get("/settings/llm/providers")
def get_llm_providers():
    """Get all configured LLM providers (API keys masked)."""
    return {"providers": LLMService.get_providers()}

@app.post("/settings/llm/providers")
def add_llm_provider(req: LLMProviderRequest):
    """Add a new LLM provider."""
    provider = LLMService.add_provider(
        name=req.name or "",
        provider_type=req.type,
        base_url=req.base_url,
        api_key=req.api_key or ""
    )
    # Save to disk
    music_service.current_settings["llm_providers"] = LLMService.get_providers_raw()
    music_service._save_settings()
    # Return masked
    masked = dict(provider)
    key = masked.get("api_key", "")
    masked["api_key"] = f"***{key[-4:]}" if key and len(key) > 4 else ""
    return masked

@app.put("/settings/llm/providers/{provider_id}")
def update_llm_provider(provider_id: str, req: LLMProviderRequest):
    """Update an existing LLM provider."""
    try:
        updates = {}
        if req.name is not None:
            updates["name"] = req.name
        if req.base_url:
            updates["base_url"] = req.base_url
        if req.api_key is not None:
            updates["api_key"] = req.api_key
        if req.enabled is not None:
            updates["enabled"] = req.enabled
        if req.type:
            updates["type"] = req.type

        provider = LLMService.update_provider(provider_id, **updates)
        music_service.current_settings["llm_providers"] = LLMService.get_providers_raw()
        music_service._save_settings()

        masked = dict(provider)
        key = masked.get("api_key", "")
        masked["api_key"] = f"***{key[-4:]}" if key and len(key) > 4 else ""
        return masked
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/settings/llm/providers/{provider_id}")
def delete_llm_provider(provider_id: str):
    """Delete a LLM provider."""
    if LLMService.delete_provider(provider_id):
        music_service.current_settings["llm_providers"] = LLMService.get_providers_raw()
        music_service._save_settings()
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Provider not found")

@app.post("/settings/llm/providers/{provider_id}/fetch-models")
def fetch_provider_models(provider_id: str):
    """Fetch available models from a provider's API."""
    try:
        models = LLMService.fetch_models(provider_id)
        music_service.current_settings["llm_providers"] = LLMService.get_providers_raw()
        music_service._save_settings()
        return {"models": models}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/settings/llm/providers/{provider_id}/toggle-model")
def toggle_provider_model(provider_id: str, req: LLMToggleModelRequest):
    """Enable or disable a specific model for a provider."""
    if LLMService.toggle_model(provider_id, req.model_id, req.enabled):
        music_service.current_settings["llm_providers"] = LLMService.get_providers_raw()
        music_service._save_settings()
        return {"status": "ok", "model_id": req.model_id, "enabled": req.enabled}
    raise HTTPException(status_code=404, detail="Provider not found")


# ============== VERTEX AI / VIDEO GENERATION ==============

@app.get("/settings/vertex_ai")
def get_vertex_ai_status():
    """Get Vertex AI configuration status."""
    return vertex_ai_service.get_status()


@app.post("/settings/vertex_ai")
def configure_vertex_ai(req: VertexAISettingsRequest):
    """Configure Vertex AI credentials."""
    if not req.service_account_json or not req.project_id:
        raise HTTPException(status_code=400, detail="service_account_json and project_id are required")
    try:
        vertex_ai_service.configure(
            service_account_json=req.service_account_json,
            project_id=req.project_id,
            location=req.location or "us-central1",
        )
        # Save to settings
        music_service.current_settings["vertex_ai"] = vertex_ai_service.get_settings_for_save()
        music_service._save_settings()
        return {"status": "ok", **vertex_ai_service.get_status()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/settings/vertex_ai")
def remove_vertex_ai():
    """Remove Vertex AI credentials."""
    vertex_ai_service._configured = False
    vertex_ai_service._credentials = None
    vertex_ai_service._project_id = None
    vertex_ai_service._credentials_json = None
    music_service.current_settings.pop("vertex_ai", None)
    music_service._save_settings()
    return {"status": "removed"}


@app.post("/generate/video")
async def generate_video(req: VideoGenerateRequest, background_tasks: BackgroundTasks):
    """Start AI music video generation for a song."""
    if not vertex_ai_service.is_configured():
        raise HTTPException(status_code=400, detail="Vertex AI not configured. Go to Settings > Vertex AI.")

    # Find the music job
    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.id == UUID(req.job_id))).first()
        if not job:
            raise HTTPException(status_code=404, detail="Music job not found")
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Music generation must be completed first")
        if not job.audio_path:
            raise HTTPException(status_code=400, detail="No audio file found for this job")

        # Create video job
        video_job = VideoJob(
            job_id=UUID(req.job_id),
            mode=req.mode,
            custom_prompt=req.custom_prompt,
            style_preset=req.style_preset,
        )
        session.add(video_job)
        session.commit()
        session.refresh(video_job)
        video_job_id = str(video_job.id)

        # Resolve audio path
        audio_path = job.audio_path
        if audio_path.startswith("/audio/"):
            audio_path = os.path.join("backend/generated_audio", audio_path.replace("/audio/", ""))

        # Start background generation
        background_tasks.add_task(
            video_service.generate_video,
            video_job_id=video_job_id,
            music_job_id=req.job_id,
            audio_path=audio_path,
            title=job.title or "",
            lyrics=job.lyrics or "",
            tags=job.tags or "",
            duration_ms=job.duration_ms,
            mode=req.mode,
            custom_prompt=req.custom_prompt,
            style_preset=req.style_preset,
            db_engine=engine,
            event_manager=event_manager,
        )

    return {
        "video_job_id": video_job_id,
        "status": "queued",
        "message": "Video generation started",
    }


@app.get("/video_jobs/{video_job_id}")
def get_video_job(video_job_id: str):
    """Get video job status and details."""
    with Session(engine) as session:
        job = session.exec(
            select(VideoJob).where(VideoJob.id == UUID(video_job_id))
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="Video job not found")
        return {
            "id": str(job.id),
            "job_id": str(job.job_id),
            "status": job.status,
            "mode": job.mode,
            "style_preset": job.style_preset,
            "total_clips": job.total_clips,
            "completed_clips": job.completed_clips,
            "video_path": job.video_path,
            "error_msg": job.error_msg,
            "created_at": job.created_at.isoformat(),
            "generation_time_seconds": job.generation_time_seconds,
        }


@app.post("/video_jobs/{video_job_id}/cancel")
def cancel_video_job(video_job_id: str):
    """Cancel a running video generation job."""
    if video_service.cancel_job(video_job_id):
        return {"status": "cancelling", "video_job_id": video_job_id}
    raise HTTPException(status_code=404, detail="Video job not found or not active")


@app.get("/jobs/{job_id}/video")
def get_latest_video_for_song(job_id: str):
    """Get the latest video job for a music track."""
    with Session(engine) as session:
        video_job = session.exec(
            select(VideoJob)
            .where(VideoJob.job_id == UUID(job_id))
            .order_by(VideoJob.created_at.desc())
        ).first()
        if not video_job:
            return {"video_job": None}
        return {
            "video_job": {
                "id": str(video_job.id),
                "status": video_job.status,
                "video_path": video_job.video_path,
                "style_preset": video_job.style_preset,
                "total_clips": video_job.total_clips,
                "completed_clips": video_job.completed_clips,
                "error_msg": video_job.error_msg,
                "generation_time_seconds": video_job.generation_time_seconds,
            }
        }


@app.get("/download_video/{video_job_id}")
def download_video(video_job_id: str):
    """Download generated video file."""
    with Session(engine) as session:
        job = session.exec(
            select(VideoJob).where(VideoJob.id == UUID(video_job_id))
        ).first()
        if not job or not job.video_path:
            raise HTTPException(status_code=404, detail="Video not found")

        # video_path is like /video/{job_id}/music_video.mp4
        file_path = os.path.join(VIDEO_OUTPUT_DIR, video_job_id, "music_video.mp4")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Video file not found on disk")

        return FileResponse(
            file_path,
            media_type="video/mp4",
            filename=f"music_video_{video_job_id[:8]}.mp4",
        )


# ============== FRONTEND STATIC FILES (Docker Production) ==============
# Serve frontend static files if the dist folder exists (Docker deployment)
FRONTEND_DIST = "frontend/dist"
if os.path.exists(FRONTEND_DIST):
    # Serve static assets (js, css, images)
    app.mount("/assets", StaticFiles(directory=f"{FRONTEND_DIST}/assets"), name="frontend_assets")

    # Catch-all route for SPA - must be last
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # Check if it's a static file
        file_path = os.path.join(FRONTEND_DIST, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_graceful_shutdown=1)
