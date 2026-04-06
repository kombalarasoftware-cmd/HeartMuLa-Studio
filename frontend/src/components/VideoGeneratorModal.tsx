import { useState, useEffect } from 'react';
import { X, Video, Play, Film, Sparkles, Loader2, Download, XCircle, Pause } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';
import type { VideoJob, Job } from '../api';

const STYLE_PRESETS = [
    { id: 'cinematic', label: 'Cinematic', emoji: '🎬' },
    { id: 'anime', label: 'Anime', emoji: '🎨' },
    { id: 'realistic', label: 'Realistic', emoji: '📷' },
    { id: 'abstract', label: 'Abstract', emoji: '🌀' },
    { id: 'retro', label: 'Retro', emoji: '📼' },
    { id: 'noir', label: 'Film Noir', emoji: '🖤' },
];

interface VideoGeneratorModalProps {
    isOpen: boolean;
    onClose: () => void;
    darkMode: boolean;
    job: Job | null;
    videoJob: VideoJob | null;
    onVideoJobUpdate: (videoJob: VideoJob) => void;
}

export function VideoGeneratorModal({
    isOpen,
    onClose,
    darkMode,
    job,
    videoJob,
    onVideoJobUpdate,
}: VideoGeneratorModalProps) {
    const [mode, setMode] = useState<'auto' | 'manual'>('auto');
    const [stylePreset, setStylePreset] = useState('cinematic');
    const [customPrompt, setCustomPrompt] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentVideoJob, setCurrentVideoJob] = useState<VideoJob | null>(videoJob);

    useEffect(() => {
        setCurrentVideoJob(videoJob);
    }, [videoJob]);

    // Poll for video job status when generating
    useEffect(() => {
        if (!currentVideoJob) return;
        if (currentVideoJob.status === 'completed' || currentVideoJob.status === 'failed') return;

        const interval = setInterval(async () => {
            try {
                const updated = await api.getVideoJob(currentVideoJob.id);
                setCurrentVideoJob(updated);
                onVideoJobUpdate(updated);
            } catch {}
        }, 3000);

        return () => clearInterval(interval);
    }, [currentVideoJob?.id, currentVideoJob?.status, onVideoJobUpdate]);

    const handleGenerate = async () => {
        if (!job) return;
        setIsGenerating(true);
        setError(null);
        try {
            const result = await api.generateVideo(
                job.id,
                mode,
                stylePreset,
                mode === 'manual' ? customPrompt : undefined
            );
            const newJob = await api.getVideoJob(result.video_job_id);
            setCurrentVideoJob(newJob);
            onVideoJobUpdate(newJob);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to start video generation');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleCancel = async () => {
        if (!currentVideoJob) return;
        try {
            await api.cancelVideoJob(currentVideoJob.id);
        } catch {}
    };

    const getProgressText = () => {
        if (!currentVideoJob) return '';
        switch (currentVideoJob.status) {
            case 'queued': return 'Queued...';
            case 'generating_prompts': return 'AI is analyzing the song...';
            case 'generating_clips': return `Generating clip ${currentVideoJob.completed_clips}/${currentVideoJob.total_clips}...`;
            case 'merging': return 'Merging clips and adding audio...';
            case 'completed': return 'Video ready!';
            case 'failed': return currentVideoJob.error_msg || 'Generation failed';
            default: return '';
        }
    };

    const getProgress = () => {
        if (!currentVideoJob) return 0;
        switch (currentVideoJob.status) {
            case 'queued': return 2;
            case 'generating_prompts': return 5;
            case 'generating_clips':
                if (currentVideoJob.total_clips === 0) return 10;
                return 5 + Math.round((currentVideoJob.completed_clips / currentVideoJob.total_clips) * 85);
            case 'merging': return 92;
            case 'completed': return 100;
            default: return 0;
        }
    };

    const isActive = currentVideoJob && !['completed', 'failed'].includes(currentVideoJob.status);
    const isCompleted = currentVideoJob?.status === 'completed';
    const videoUrl = currentVideoJob?.video_path;

    const inputClass = `w-full px-3 py-2 rounded-lg text-sm ${
        darkMode
            ? 'bg-[#1a1a1a] border border-[#333] text-white placeholder-[#666]'
            : 'bg-white border border-slate-200 text-slate-900 placeholder-slate-400'
    }`;

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className={`w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden ${
                            darkMode ? 'bg-[#181818]' : 'bg-white'
                        }`}
                    >
                        {/* Header */}
                        <div className={`flex items-center justify-between px-6 py-4 border-b ${
                            darkMode ? 'border-[#282828]' : 'border-slate-200'
                        }`}>
                            <div className="flex items-center gap-3">
                                <Video className={`w-5 h-5 ${darkMode ? 'text-[#1DB954]' : 'text-cyan-500'}`} />
                                <h2 className={`text-lg font-semibold ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                                    Generate Music Video
                                </h2>
                            </div>
                            <button
                                onClick={onClose}
                                className={`p-2 rounded-full transition-colors ${
                                    darkMode ? 'hover:bg-[#282828] text-[#b3b3b3]' : 'hover:bg-slate-100 text-slate-500'
                                }`}
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="px-6 py-4 max-h-[70vh] overflow-y-auto space-y-4">
                            {/* Song info */}
                            {job && (
                                <div className={`rounded-lg p-3 ${darkMode ? 'bg-[#282828]' : 'bg-slate-50'}`}>
                                    <p className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                                        {job.title || job.prompt}
                                    </p>
                                    {job.tags && (
                                        <p className={`text-xs mt-1 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                            {job.tags}
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* Video preview (if completed) */}
                            {isCompleted && videoUrl && (
                                <div className="rounded-lg overflow-hidden">
                                    <video
                                        src={videoUrl}
                                        controls
                                        className="w-full rounded-lg"
                                        style={{ maxHeight: '300px' }}
                                    />
                                    <div className="flex gap-2 mt-2">
                                        <a
                                            href={videoUrl}
                                            download
                                            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                                darkMode
                                                    ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                                    : 'bg-cyan-500 text-white hover:bg-cyan-600'
                                            }`}
                                        >
                                            <Download className="w-4 h-4" />
                                            Download Video
                                        </a>
                                    </div>
                                    {currentVideoJob?.generation_time_seconds && (
                                        <p className={`text-xs mt-2 text-center ${darkMode ? 'text-[#666]' : 'text-slate-400'}`}>
                                            Generated in {Math.round(currentVideoJob.generation_time_seconds)}s
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* Progress bar (when generating) */}
                            {isActive && (
                                <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                        <Loader2 className={`w-4 h-4 animate-spin ${darkMode ? 'text-[#1DB954]' : 'text-cyan-500'}`} />
                                        <span className={`text-sm ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                                            {getProgressText()}
                                        </span>
                                    </div>
                                    <div className={`w-full h-2 rounded-full overflow-hidden ${
                                        darkMode ? 'bg-[#383838]' : 'bg-slate-200'
                                    }`}>
                                        <motion.div
                                            className={`h-full rounded-full ${darkMode ? 'bg-[#1DB954]' : 'bg-cyan-500'}`}
                                            initial={{ width: 0 }}
                                            animate={{ width: `${getProgress()}%` }}
                                            transition={{ duration: 0.5 }}
                                        />
                                    </div>
                                    <button
                                        onClick={handleCancel}
                                        className={`flex items-center gap-1 text-xs transition-colors ${
                                            darkMode ? 'text-red-400 hover:text-red-300' : 'text-red-500 hover:text-red-600'
                                        }`}
                                    >
                                        <Pause className="w-3 h-3" />
                                        Cancel generation
                                    </button>
                                </div>
                            )}

                            {/* Failed state */}
                            {currentVideoJob?.status === 'failed' && (
                                <div className={`rounded-lg p-3 flex items-start gap-2 ${
                                    darkMode ? 'bg-red-900/20 border border-red-800/50' : 'bg-red-50 border border-red-200'
                                }`}>
                                    <XCircle className={`w-4 h-4 mt-0.5 ${darkMode ? 'text-red-400' : 'text-red-500'}`} />
                                    <div>
                                        <p className={`text-sm font-medium ${darkMode ? 'text-red-400' : 'text-red-700'}`}>
                                            Generation failed
                                        </p>
                                        <p className={`text-xs mt-0.5 ${darkMode ? 'text-red-400/70' : 'text-red-600'}`}>
                                            {currentVideoJob.error_msg || 'Unknown error'}
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Generation options (show when not actively generating) */}
                            {!isActive && (
                                <>
                                    {/* Mode selector */}
                                    <div>
                                        <label className={`block text-xs mb-2 font-medium ${
                                            darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'
                                        }`}>
                                            Mode
                                        </label>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setMode('auto')}
                                                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                                                    mode === 'auto'
                                                        ? darkMode ? 'bg-[#1DB954] text-black' : 'bg-cyan-500 text-white'
                                                        : darkMode ? 'bg-[#282828] text-[#b3b3b3] hover:bg-[#333]' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                                }`}
                                            >
                                                <Sparkles className="w-4 h-4" />
                                                Auto (AI Director)
                                            </button>
                                            <button
                                                onClick={() => setMode('manual')}
                                                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                                                    mode === 'manual'
                                                        ? darkMode ? 'bg-[#1DB954] text-black' : 'bg-cyan-500 text-white'
                                                        : darkMode ? 'bg-[#282828] text-[#b3b3b3] hover:bg-[#333]' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                                }`}
                                            >
                                                <Film className="w-4 h-4" />
                                                Manual (Your Vision)
                                            </button>
                                        </div>
                                    </div>

                                    {/* Manual prompt */}
                                    {mode === 'manual' && (
                                        <div>
                                            <label className={`block text-xs mb-1 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                                Describe your video vision
                                            </label>
                                            <textarea
                                                value={customPrompt}
                                                onChange={(e) => setCustomPrompt(e.target.value)}
                                                placeholder="e.g. A lonely astronaut floating through colorful nebulas, discovering ancient alien ruins on a distant planet..."
                                                rows={3}
                                                className={`${inputClass} resize-none`}
                                            />
                                        </div>
                                    )}

                                    {/* Style presets */}
                                    <div>
                                        <label className={`block text-xs mb-2 font-medium ${
                                            darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'
                                        }`}>
                                            Visual Style
                                        </label>
                                        <div className="grid grid-cols-3 gap-2">
                                            {STYLE_PRESETS.map((style) => (
                                                <button
                                                    key={style.id}
                                                    onClick={() => setStylePreset(style.id)}
                                                    className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                                                        stylePreset === style.id
                                                            ? darkMode ? 'bg-[#1DB954] text-black' : 'bg-cyan-500 text-white'
                                                            : darkMode ? 'bg-[#282828] text-[#b3b3b3] hover:bg-[#333]' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                                    }`}
                                                >
                                                    {style.emoji} {style.label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Info */}
                                    <p className={`text-xs ${darkMode ? 'text-[#666]' : 'text-slate-400'}`}>
                                        {mode === 'auto'
                                            ? 'AI will analyze the song (audio + lyrics) and create a multi-scene music video with matching visuals.'
                                            : 'Describe your creative vision. AI will generate scenes based on your description while matching the song.'}
                                    </p>
                                </>
                            )}

                            {error && (
                                <p className={`text-xs ${darkMode ? 'text-red-400' : 'text-red-500'}`}>{error}</p>
                            )}
                        </div>

                        {/* Footer */}
                        {!isActive && !isCompleted && (
                            <div className={`px-6 py-4 border-t ${darkMode ? 'border-[#282828]' : 'border-slate-200'}`}>
                                <button
                                    onClick={handleGenerate}
                                    disabled={isGenerating || (mode === 'manual' && !customPrompt.trim())}
                                    className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                                        darkMode
                                            ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                            : 'bg-cyan-500 text-white hover:bg-cyan-600'
                                    }`}
                                >
                                    {isGenerating ? (
                                        <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</>
                                    ) : (
                                        <><Play className="w-4 h-4" /> Generate Music Video</>
                                    )}
                                </button>
                            </div>
                        )}

                        {/* Regenerate button (when completed or failed) */}
                        {(isCompleted || currentVideoJob?.status === 'failed') && (
                            <div className={`px-6 py-4 border-t ${darkMode ? 'border-[#282828]' : 'border-slate-200'}`}>
                                <button
                                    onClick={handleGenerate}
                                    disabled={isGenerating}
                                    className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                                        darkMode
                                            ? 'bg-[#282828] text-white hover:bg-[#333] border border-[#404040]'
                                            : 'bg-slate-100 text-slate-800 hover:bg-slate-200 border border-slate-200'
                                    }`}
                                >
                                    <Video className="w-4 h-4" />
                                    Regenerate Video
                                </button>
                            </div>
                        )}
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
}
