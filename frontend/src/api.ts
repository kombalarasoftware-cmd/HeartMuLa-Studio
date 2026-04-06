import axios from 'axios';

// Use same origin for reverse proxy setups, fallback to :8000 for dev/Docker
const API_BASE_URL = import.meta.env.DEV
    ? `http://${window.location.hostname}:8000`  // Dev mode: explicit port 8000
    : `${window.location.protocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}`;  // Production: same origin

// Axios interceptor for JWT auth
const axiosInstance = axios.create();

axiosInstance.interceptors.request.use((config) => {
    const token = localStorage.getItem('heartmula_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

axiosInstance.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('heartmula_token');
            localStorage.removeItem('heartmula_user');
            window.location.reload();
        }
        return Promise.reject(error);
    }
);

export interface Job {
    id: string;
    status: 'queued' | 'processing' | 'completed' | 'failed';
    title?: string;
    prompt: string;
    lyrics?: string;
    tags?: string;
    audio_path?: string;
    error_msg?: string;
    created_at: string;
    duration_ms?: number;
    seed?: number;
    generation_time_seconds?: number;
}

export interface LLMModel {
    id: string;
    name: string;
    provider_id: string;
    provider_name: string;
    provider_type: string;
}

export interface LLMProviderModel {
    id: string;
    name: string;
}

export interface LLMProvider {
    id: string;
    name: string;
    type: 'openai' | 'ollama';
    base_url: string;
    api_key: string;   // masked
    enabled: boolean;
    models: LLMProviderModel[];
    enabled_models: string[];
}

export interface Playlist {
    id: string;
    name: string;
    description?: string;
    cover_seed?: string;
    song_count: number;
    created_at: string;
    updated_at: string;
}

export interface PlaylistWithSongs extends Playlist {
    songs: {
        job: Job;
        position: number;
        added_at: string;
    }[];
}

export interface StartupStatus {
    status: 'not_started' | 'downloading' | 'loading' | 'ready' | 'error';
    progress: number;
    message: string;
    error?: string | null;
    ready: boolean;
}

export interface GPUInfo {
    index: number;
    name: string;
    vram_gb: number;
    compute_capability: number;
    supports_flash_attention: boolean;
}

export interface GPUStatus {
    cuda_available: boolean;
    num_gpus: number;
    gpus: GPUInfo[];
    total_vram_gb: number;
}

export interface GPUSettings {
    quantization_4bit: string;
    sequential_offload: string;
    torch_compile: boolean;
    torch_compile_mode: string;
    mmgp_quantization: string;  // "true" for INT8, "false" for bf16
}

// LLMSettings kept for backward compat type reference but not used in new provider flow

export interface TranscriptorStatus {
    available: boolean;
    model_downloaded: boolean;
    model_loaded: boolean;
    is_loading: boolean;
    demucs_available: boolean;
    device: string;
}

export interface TranscriptionChunk {
    text: string;
    timestamp: [number, number];
}

export interface TranscriptionResult {
    text: string;
    chunks: TranscriptionChunk[];
}

export interface VideoJob {
    id: string;
    job_id: string;
    status: 'queued' | 'generating_prompts' | 'generating_clips' | 'merging' | 'completed' | 'failed';
    mode: string;
    style_preset: string;
    total_clips: number;
    completed_clips: number;
    video_path?: string;
    error_msg?: string;
    created_at: string;
    generation_time_seconds?: number;
}

export interface VertexAIStatus {
    configured: boolean;
    project_id?: string;
    location?: string;
}

export const api = {
    checkHealth: async () => {
        const res = await axiosInstance.get(`${API_BASE_URL}/health`);
        return res.data;
    },

    getLyricsModels: async (): Promise<LLMModel[]> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/models/lyrics`);
        return res.data.models;
    },

    getLanguages: async (): Promise<string[]> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/languages`);
        return res.data.languages;
    },

    generateJob: async (
        prompt: string,
        durationMs: number,
        lyrics?: string,
        tags?: string,
        cfg_scale: number = 1.5,
        parentJobId?: string,
        seed?: number,
        refAudioId?: string,
        styleInfluence: number = 100.0,
        refAudioStartSec?: number,
        negativeTags?: string,
        refAudioAsNoise?: boolean,
        refAudioNoiseStrength?: number,
        title?: string
    ) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/music`, {
            prompt,
            duration_ms: durationMs,
            lyrics,
            tags,
            cfg_scale,
            parent_job_id: parentJobId,
            seed,
            ref_audio_id: refAudioId,
            style_influence: styleInfluence,
            ref_audio_start_sec: refAudioStartSec,
            // Experimental: Advanced reference audio options
            negative_tags: negativeTags,
            ref_audio_as_noise: refAudioAsNoise,
            ref_audio_noise_strength: refAudioNoiseStrength,
            // User-defined title
            title
        });
        return res.data;
    },

    generateLyrics: async (topic: string, modelId: string, providerId: string, currentLyrics?: string, language: string = "English", durationSeconds?: number) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/lyrics`, {
            topic,
            model_name: modelId,
            provider: providerId,
            seed_lyrics: currentLyrics,
            language,
            duration_seconds: durationSeconds
        });
        return {
            lyrics: res.data.lyrics,
            suggested_topic: res.data.suggested_topic,
            suggested_tags: res.data.suggested_tags
        };
    },

    enhancePrompt: async (concept: string, modelId: string, providerId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/enhance_prompt`, {
            concept,
            model_name: modelId,
            provider: providerId
        });
        return res.data;
    },

    getInspiration: async (modelId: string, providerId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/evaluate_inspiration`, {
            model_name: modelId,
            provider: providerId
        });
        return res.data;
    },

    getStylePresets: async (modelId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/styles`, {
            model_name: modelId
        });
        return res.data.styles;
    },

    generateMusic: async (
        tags: string,
        lyrics: string,
        durationMs: number = 240000,
        temperature: number = 1.0,
        cfgScale: number = 1.5,
        topk: number = 50,
        prompt: string,
        llmModel: string = "llama3",
        refAudioId?: string
    ) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/music`, {
            lyrics,
            tags,
            duration_ms: durationMs,
            temperature,
            cfg_scale: cfgScale,
            topk,
            prompt,
            llm_model: llmModel,
            ref_audio_id: refAudioId
        });
        return res.data;
    },

    // ============== REFERENCE AUDIO ==============

    uploadRefAudio: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const res = await axiosInstance.post(`${API_BASE_URL}/upload/ref_audio`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        return res.data as { id: string; filename: string; path: string; size: number };
    },

    deleteRefAudio: async (fileId: string) => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/upload/ref_audio/${fileId}`);
        return res.data;
    },

    renameJob: async (jobId: string, title: string) => {
        const res = await axiosInstance.patch(`${API_BASE_URL}/jobs/${jobId}`, { title });
        return res.data;
    },

    deleteJob: async (jobId: string) => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/jobs/${jobId}`);
        return res.data;
    },

    cancelJob: async (jobId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/jobs/${jobId}/cancel`);
        return res.data;
    },

    getJobStatus: async (jobId: string) => {
        const res = await axiosInstance.get<Job>(`${API_BASE_URL}/jobs/${jobId}`);
        return res.data;
    },

    getHistory: async () => {
        const res = await axiosInstance.get<Job[]>(`${API_BASE_URL}/history`);
        return res.data;
    },

    getAudioUrl: (path: string) => {
        return `${API_BASE_URL}${path}`;
    },

    getDownloadUrl: (jobId: string) => {
        return `${API_BASE_URL}/download_track/${jobId}`;
    },

    connectToEvents: (onMessage: (event: MessageEvent) => void) => {
        const eventSource = new EventSource(`${API_BASE_URL}/events`);
        eventSource.onmessage = onMessage;

        // Listen to all event types from backend
        eventSource.addEventListener("job_update", onMessage);
        eventSource.addEventListener("job_progress", onMessage);
        eventSource.addEventListener("job_queued", onMessage);
        eventSource.addEventListener("job_queue", onMessage);
        eventSource.addEventListener("startup_progress", onMessage);

        return eventSource;
    },

    // ============== LIKES (Favorites) ==============

    likeSong: async (jobId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/songs/${jobId}/like`);
        return res.data;
    },

    unlikeSong: async (jobId: string) => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/songs/${jobId}/like`);
        return res.data;
    },

    getLikedSongs: async () => {
        const res = await axiosInstance.get(`${API_BASE_URL}/songs/liked`);
        return res.data as { songs: Job[]; liked_ids: string[] };
    },

    getLikedSongIds: async () => {
        const res = await axiosInstance.get(`${API_BASE_URL}/songs/liked/ids`);
        return res.data.liked_ids as string[];
    },

    // ============== PLAYLISTS ==============

    getPlaylists: async () => {
        const res = await axiosInstance.get(`${API_BASE_URL}/playlists`);
        return res.data.playlists as Playlist[];
    },

    createPlaylist: async (name: string, description?: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/playlists`, { name, description });
        return res.data as Playlist;
    },

    getPlaylist: async (playlistId: string) => {
        const res = await axiosInstance.get(`${API_BASE_URL}/playlists/${playlistId}`);
        return res.data as PlaylistWithSongs;
    },

    updatePlaylist: async (playlistId: string, name?: string, description?: string) => {
        const res = await axiosInstance.patch(`${API_BASE_URL}/playlists/${playlistId}`, { name, description });
        return res.data;
    },

    deletePlaylist: async (playlistId: string) => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/playlists/${playlistId}`);
        return res.data;
    },

    addSongToPlaylist: async (playlistId: string, jobId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/playlists/${playlistId}/songs`, { job_id: jobId });
        return res.data;
    },

    removeSongFromPlaylist: async (playlistId: string, jobId: string) => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/playlists/${playlistId}/songs/${jobId}`);
        return res.data;
    },

    // ============== STARTUP & SETTINGS ==============

    getStartupStatus: async (): Promise<StartupStatus> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/settings/startup/status`);
        return res.data;
    },

    getGPUStatus: async (): Promise<GPUStatus> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/settings/gpu/status`);
        return res.data;
    },

    getGPUSettings: async (): Promise<GPUSettings> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/settings/gpu`);
        return res.data;
    },

    updateGPUSettings: async (settings: Partial<GPUSettings>): Promise<GPUSettings> => {
        const res = await axiosInstance.put(`${API_BASE_URL}/settings/gpu`, settings);
        return res.data;
    },

    reloadModels: async (settings: Partial<GPUSettings>): Promise<{ status: string; message: string }> => {
        const res = await axiosInstance.post(`${API_BASE_URL}/settings/gpu/reload`, settings);
        return res.data;
    },

    // ============== LLM PROVIDERS ==============

    getLLMProviders: async (): Promise<LLMProvider[]> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/settings/llm/providers`);
        return res.data.providers;
    },

    addLLMProvider: async (provider: { name?: string; type: string; base_url: string; api_key?: string }): Promise<LLMProvider> => {
        const res = await axiosInstance.post(`${API_BASE_URL}/settings/llm/providers`, provider);
        return res.data;
    },

    updateLLMProvider: async (providerId: string, updates: { name?: string; type?: string; base_url?: string; api_key?: string; enabled?: boolean }): Promise<LLMProvider> => {
        const res = await axiosInstance.put(`${API_BASE_URL}/settings/llm/providers/${providerId}`, updates);
        return res.data;
    },

    deleteLLMProvider: async (providerId: string) => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/settings/llm/providers/${providerId}`);
        return res.data;
    },

    fetchProviderModels: async (providerId: string): Promise<LLMProviderModel[]> => {
        const res = await axiosInstance.post(`${API_BASE_URL}/settings/llm/providers/${providerId}/fetch-models`);
        return res.data.models;
    },

    toggleProviderModel: async (providerId: string, modelId: string, enabled: boolean) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/settings/llm/providers/${providerId}/toggle-model`, {
            model_id: modelId,
            enabled
        });
        return res.data;
    },

    // ============== TRANSCRIPTION (HeartTranscriptor) ==============

    getTranscriptorStatus: async (): Promise<TranscriptorStatus> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/transcriptor/status`);
        return res.data;
    },

    downloadTranscriptor: async () => {
        const res = await axiosInstance.post(`${API_BASE_URL}/transcriptor/download`);
        return res.data as { status: string; message: string };
    },

    loadTranscriptor: async () => {
        const res = await axiosInstance.post(`${API_BASE_URL}/transcriptor/load`);
        return res.data as { status: string; message: string };
    },

    unloadTranscriptor: async () => {
        const res = await axiosInstance.post(`${API_BASE_URL}/transcriptor/unload`);
        return res.data as { status: string; message: string };
    },

    transcribeAudio: async (file: File, useDemucs: boolean = false): Promise<TranscriptionResult> => {
        const formData = new FormData();
        formData.append('file', file);
        const res = await axiosInstance.post(
            `${API_BASE_URL}/transcriptor/transcribe?use_demucs=${useDemucs}`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000 }
        );
        return res.data;
    },

    transcribeJobAudio: async (jobId: string, useDemucs: boolean = false): Promise<TranscriptionResult> => {
        const res = await axiosInstance.post(
            `${API_BASE_URL}/transcriptor/transcribe/${jobId}?use_demucs=${useDemucs}`,
            {},
            { timeout: 300000 }
        );
        return res.data;
    },

    // ============== Vertex AI / Video ==============

    getVertexAIStatus: async (): Promise<VertexAIStatus> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/settings/vertex_ai`);
        return res.data;
    },

    configureVertexAI: async (serviceAccountJson: string, projectId: string, location: string = 'us-central1') => {
        const res = await axiosInstance.post(`${API_BASE_URL}/settings/vertex_ai`, {
            service_account_json: serviceAccountJson,
            project_id: projectId,
            location,
        });
        return res.data;
    },

    removeVertexAI: async () => {
        const res = await axiosInstance.delete(`${API_BASE_URL}/settings/vertex_ai`);
        return res.data;
    },

    generateVideo: async (jobId: string, mode: string = 'auto', stylePreset: string = 'cinematic', customPrompt?: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/generate/video`, {
            job_id: jobId,
            mode,
            style_preset: stylePreset,
            custom_prompt: customPrompt,
        });
        return res.data as { video_job_id: string; status: string; message: string };
    },

    getVideoJob: async (videoJobId: string): Promise<VideoJob> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/video_jobs/${videoJobId}`);
        return res.data;
    },

    cancelVideoJob: async (videoJobId: string) => {
        const res = await axiosInstance.post(`${API_BASE_URL}/video_jobs/${videoJobId}/cancel`);
        return res.data;
    },

    getLatestVideoForSong: async (jobId: string): Promise<{ video_job: VideoJob | null }> => {
        const res = await axiosInstance.get(`${API_BASE_URL}/jobs/${jobId}/video`);
        return res.data;
    },

    // ============== AUTH ==============

    setAuthToken: (token: string | null) => {
        if (token) {
            axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        } else {
            delete axiosInstance.defaults.headers.common['Authorization'];
        }
    },
};
