"""
Video Service — AI Music Video Clip Generator.

Multi-clip pipeline:
1. Gemini sahne senaryosu yazar (audio + lyrics analizi)
2. Veo 3.1 ile clip'ler paralel üretilir
3. FFmpeg ile birleştirilir + audio eklenir
4. Final MP4 video
"""
import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any

from backend.app.services.vertex_ai_service import vertex_ai_service, STYLE_PRESETS

logger = logging.getLogger(__name__)

VIDEO_OUTPUT_DIR = os.environ.get("VIDEO_OUTPUT_DIR", "backend/generated_videos")
CLIP_DURATION = 8  # Veo 3.1 max ~8 sn
MAX_PARALLEL_CLIPS = 3  # Aynı anda max Veo isteği


class VideoService:
    """AI Music Video üretim servisi."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.active_jobs: Dict[str, Dict[str, Any]] = {}
            inst._semaphore = asyncio.Semaphore(MAX_PARALLEL_CLIPS)
            cls._instance = inst
        return cls._instance

    async def generate_video(
        self,
        video_job_id: str,
        music_job_id: str,
        audio_path: str,
        title: str,
        lyrics: str,
        tags: str,
        duration_ms: int,
        mode: str = "auto",
        custom_prompt: Optional[str] = None,
        style_preset: str = "cinematic",
        db_engine=None,
        event_manager=None,
    ):
        """Ana video üretim pipeline'ı — background task olarak çalışır."""
        start_time = time.time()
        job_dir = Path(VIDEO_OUTPUT_DIR) / video_job_id
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        self.active_jobs[video_job_id] = {"cancelled": False}

        try:
            # ---- Adım 1: Sahne prompt'ları üret ----
            self._emit_progress(event_manager, video_job_id, "generating_prompts", 0,
                              "AI is analyzing the song...")
            await self._update_job_status(db_engine, video_job_id, "generating_prompts")

            scene_prompts = await vertex_ai_service.generate_scene_prompts(
                audio_path=audio_path,
                title=title or "Untitled",
                lyrics=lyrics or "",
                tags=tags or "",
                duration_ms=duration_ms,
                mode=mode,
                custom_prompt=custom_prompt,
                style_preset=style_preset,
                clip_duration=CLIP_DURATION,
            )

            total_clips = len(scene_prompts)
            await self._update_job_fields(db_engine, video_job_id, {
                "scene_prompts": json.dumps(scene_prompts),
                "total_clips": total_clips,
            })

            if self._is_cancelled(video_job_id):
                raise asyncio.CancelledError("Job cancelled by user")

            # ---- Adım 2: Clip'leri paralel üret ----
            self._emit_progress(event_manager, video_job_id, "generating_clips", 5,
                              f"Generating {total_clips} video clips...")
            await self._update_job_status(db_engine, video_job_id, "generating_clips")

            style_prefix = STYLE_PRESETS.get(style_preset, "")
            clip_paths = await self._generate_clips_parallel(
                scene_prompts=scene_prompts,
                clips_dir=clips_dir,
                style_prefix=style_prefix,
                video_job_id=video_job_id,
                total_clips=total_clips,
                db_engine=db_engine,
                event_manager=event_manager,
            )

            if self._is_cancelled(video_job_id):
                raise asyncio.CancelledError("Job cancelled by user")

            # ---- Adım 3: FFmpeg ile birleştir ----
            self._emit_progress(event_manager, video_job_id, "merging", 90,
                              "Merging clips and adding audio...")
            await self._update_job_status(db_engine, video_job_id, "merging")

            output_path = str(job_dir / "music_video.mp4")
            await self._merge_clips_with_ffmpeg(clip_paths, audio_path, output_path)

            # ---- Adım 4: Tamamlandı ----
            elapsed = time.time() - start_time
            relative_path = f"/video/{video_job_id}/music_video.mp4"

            await self._update_job_fields(db_engine, video_job_id, {
                "status": "completed",
                "video_path": relative_path,
                "generation_time_seconds": round(elapsed, 1),
            })

            self._emit_progress(event_manager, video_job_id, "completed", 100, "Video ready!")
            if event_manager:
                event_manager.publish("video_update", {
                    "video_job_id": video_job_id,
                    "job_id": music_job_id,
                    "status": "completed",
                    "video_path": relative_path,
                })

            logger.info(f"[Video] Completed {video_job_id} in {elapsed:.1f}s ({total_clips} clips)")

        except asyncio.CancelledError:
            await self._update_job_fields(db_engine, video_job_id, {
                "status": "failed",
                "error_msg": "Cancelled by user",
            })
            self._emit_progress(event_manager, video_job_id, "failed", 0, "Cancelled")

        except Exception as e:
            logger.error(f"[Video] Failed {video_job_id}: {e}")
            await self._update_job_fields(db_engine, video_job_id, {
                "status": "failed",
                "error_msg": str(e)[:500],
            })
            self._emit_progress(event_manager, video_job_id, "failed", 0,
                              f"Error: {str(e)[:200]}")
            if event_manager:
                event_manager.publish("video_update", {
                    "video_job_id": video_job_id,
                    "job_id": music_job_id,
                    "status": "failed",
                    "error": str(e)[:200],
                })

        finally:
            self.active_jobs.pop(video_job_id, None)

    async def _generate_clips_parallel(
        self,
        scene_prompts: List[Dict],
        clips_dir: Path,
        style_prefix: str,
        video_job_id: str,
        total_clips: int,
        db_engine=None,
        event_manager=None,
    ) -> List[str]:
        """Clip'leri semaphore ile paralel üret."""
        completed = 0
        clip_paths = [None] * total_clips
        lock = asyncio.Lock()

        async def generate_one(scene: Dict, index: int):
            nonlocal completed
            async with self._semaphore:
                if self._is_cancelled(video_job_id):
                    return

                clip_path = str(clips_dir / f"clip_{index:03d}.mp4")
                logger.info(f"[Video] Generating clip {index + 1}/{total_clips}")

                try:
                    video_bytes = await vertex_ai_service.generate_video_clip(
                        prompt=scene["prompt"],
                        style_prefix=style_prefix,
                        duration_sec=CLIP_DURATION,
                    )
                    with open(clip_path, "wb") as f:
                        f.write(video_bytes)

                    clip_paths[index] = clip_path

                except Exception as e:
                    logger.error(f"[Video] Clip {index} failed: {e}")
                    clip_paths[index] = None

                async with lock:
                    completed += 1
                    progress = 5 + int((completed / total_clips) * 85)
                    self._emit_progress(
                        event_manager, video_job_id, "generating_clips", progress,
                        f"Generated clip {completed}/{total_clips}"
                    )
                    await self._update_job_fields(db_engine, video_job_id, {
                        "completed_clips": completed,
                    })

        tasks = [generate_one(scene, i) for i, scene in enumerate(scene_prompts)]
        await asyncio.gather(*tasks)

        valid_paths = [p for p in clip_paths if p is not None]
        if not valid_paths:
            raise ValueError("No clips were generated successfully")

        return valid_paths

    async def _merge_clips_with_ffmpeg(
        self,
        clip_paths: List[str],
        audio_path: str,
        output_path: str,
    ):
        """FFmpeg ile clip'leri birleştir + audio ekle."""

        if len(clip_paths) == 1:
            cmd = [
                "ffmpeg", "-y",
                "-i", clip_paths[0],
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v", "-map", "1:a",
                "-shortest",
                output_path,
            ]
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, check=True, capture_output=True)
            )
        else:
            concat_file = str(Path(output_path).parent / "concat.txt")
            with open(concat_file, "w") as f:
                for path in clip_paths:
                    f.write(f"file '{os.path.abspath(path)}'\n")

            merged_video = str(Path(output_path).parent / "merged_video.mp4")

            cmd_concat = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-r", "24",
                merged_video,
            ]
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd_concat, check=True, capture_output=True)
            )

            cmd_audio = [
                "ffmpeg", "-y",
                "-i", merged_video,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v", "-map", "1:a",
                "-shortest",
                output_path,
            ]
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd_audio, check=True, capture_output=True)
            )

        logger.info(f"[Video] Merged {len(clip_paths)} clips -> {output_path}")

    def cancel_job(self, video_job_id: str) -> bool:
        if video_job_id in self.active_jobs:
            self.active_jobs[video_job_id]["cancelled"] = True
            return True
        return False

    def _is_cancelled(self, video_job_id: str) -> bool:
        return self.active_jobs.get(video_job_id, {}).get("cancelled", False)

    def _emit_progress(self, event_manager, video_job_id: str, status: str,
                       progress: int, message: str):
        if event_manager:
            event_manager.publish("video_progress", {
                "video_job_id": video_job_id,
                "status": status,
                "progress": progress,
                "message": message,
            })

    async def _update_job_status(self, db_engine, video_job_id: str, status: str):
        if not db_engine:
            return
        try:
            from sqlmodel import Session, select
            from backend.app.models import VideoJob
            with Session(db_engine) as session:
                job = session.exec(
                    select(VideoJob).where(VideoJob.id == uuid.UUID(video_job_id))
                ).first()
                if job:
                    job.status = status
                    session.commit()
        except Exception as e:
            logger.warning(f"[Video] Failed to update status: {e}")

    async def _update_job_fields(self, db_engine, video_job_id: str,
                                  fields: Dict[str, Any]):
        if not db_engine:
            return
        try:
            from sqlmodel import Session, select
            from backend.app.models import VideoJob
            with Session(db_engine) as session:
                job = session.exec(
                    select(VideoJob).where(VideoJob.id == uuid.UUID(video_job_id))
                ).first()
                if job:
                    for key, value in fields.items():
                        setattr(job, key, value)
                    session.commit()
        except Exception as e:
            logger.warning(f"[Video] Failed to update fields: {e}")


# Singleton instance
video_service = VideoService()
