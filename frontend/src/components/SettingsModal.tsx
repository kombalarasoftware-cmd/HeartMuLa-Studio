import { useState, useEffect, useCallback } from 'react';
import { X, Cpu, RefreshCw, AlertTriangle, Check, Settings2, Globe, Key, CheckCircle, XCircle, Mic, Download, Loader2, Trash2, Plus, ChevronDown, ChevronUp, Video, Upload } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { GPUStatus, StartupStatus, GPUSettings, TranscriptorStatus, LLMProvider, VertexAIStatus } from '../api';
import { api } from '../api';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
    darkMode: boolean;
    gpuStatus: GPUStatus | null;
    currentSettings: GPUSettings | null;
    onSave: (settings: GPUSettings) => Promise<void>;
    onReload: (settings: GPUSettings) => Promise<void>;
    startupStatus: StartupStatus | null;
    onProvidersChanged?: () => void;
}

export function SettingsModal({
    isOpen,
    onClose,
    darkMode,
    gpuStatus,
    currentSettings,
    onSave,
    onReload,
    startupStatus,
    onProvidersChanged
}: SettingsModalProps) {
    const [settings, setSettings] = useState<GPUSettings>({
        quantization_4bit: 'auto',
        sequential_offload: 'auto',
        torch_compile: false,
        torch_compile_mode: 'default',
        mmgp_quantization: 'false'
    });
    // Multi-provider LLM state
    const [providers, setProviders] = useState<LLMProvider[]>([]);
    const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
    const [fetchingModels, setFetchingModels] = useState<string | null>(null);
    // Add provider form
    const [showAddProvider, setShowAddProvider] = useState(false);
    const [newProviderName, setNewProviderName] = useState('');
    const [newProviderType, setNewProviderType] = useState<'openai' | 'ollama'>('openai');
    const [newProviderUrl, setNewProviderUrl] = useState('');
    const [newProviderKey, setNewProviderKey] = useState('');

    const [isSaving, setIsSaving] = useState(false);
    const [isReloading, setIsReloading] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);
    const [saveSuccess, setSaveSuccess] = useState(false);

    // Load current settings when modal opens
    useEffect(() => {
        if (currentSettings) {
            setSettings(currentSettings);
        }
    }, [currentSettings, isOpen]);

    // Load LLM providers when modal opens
    const loadProviders = useCallback(async () => {
        try {
            const data = await api.getLLMProviders();
            setProviders(data);
        } catch (e) {
            console.error('Failed to load providers:', e);
        }
    }, []);

    useEffect(() => {
        if (isOpen) {
            loadProviders();
        }
    }, [isOpen, loadProviders]);

    // Track GPU changes
    useEffect(() => {
        if (currentSettings) {
            const changed = JSON.stringify(settings) !== JSON.stringify(currentSettings);
            setHasChanges(changed);
        }
    }, [settings, currentSettings]);

    // Check if currently reloading
    const isCurrentlyReloading = startupStatus?.status === 'loading' || startupStatus?.status === 'downloading';

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(settings);
            setSaveSuccess(true);
            setTimeout(() => setSaveSuccess(false), 2000);
        } finally {
            setIsSaving(false);
        }
    };

    // Provider management
    const handleAddProvider = async () => {
        if (!newProviderUrl) return;
        try {
            await api.addLLMProvider({
                name: newProviderName || undefined,
                type: newProviderType,
                base_url: newProviderUrl,
                api_key: newProviderKey || undefined
            });
            setNewProviderName('');
            setNewProviderUrl('');
            setNewProviderKey('');
            setShowAddProvider(false);
            await loadProviders();
            onProvidersChanged?.();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Failed to add provider');
        }
    };

    const handleDeleteProvider = async (id: string) => {
        if (!confirm('Delete this provider and all its models?')) return;
        try {
            await api.deleteLLMProvider(id);
            await loadProviders();
            onProvidersChanged?.();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Failed to delete provider');
        }
    };

    const handleFetchModels = async (providerId: string) => {
        setFetchingModels(providerId);
        try {
            await api.fetchProviderModels(providerId);
            await loadProviders();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Failed to fetch models. Check your API key and URL.');
        } finally {
            setFetchingModels(null);
        }
    };

    const handleToggleModel = async (providerId: string, modelId: string, enabled: boolean) => {
        try {
            await api.toggleProviderModel(providerId, modelId, enabled);
            await loadProviders();
            onProvidersChanged?.();
        } catch (e) {
            console.error('Failed to toggle model:', e);
        }
    };

    const handleUpdateProvider = async (providerId: string, updates: { name?: string; base_url?: string; api_key?: string; enabled?: boolean }) => {
        try {
            await api.updateLLMProvider(providerId, updates);
            await loadProviders();
            onProvidersChanged?.();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Failed to update provider');
        }
    };

    const handleReload = async () => {
        setIsReloading(true);
        try {
            await onReload(settings);
            // Don't close modal - let user see reload progress
        } catch (error: any) {
            alert(error.message || 'Failed to reload models');
            setIsReloading(false);
        }
    };

    // Reset isReloading when reload completes
    useEffect(() => {
        if (startupStatus?.status === 'ready' && isReloading) {
            setIsReloading(false);
        }
    }, [startupStatus?.status, isReloading]);

    if (!isOpen) return null;

    const selectClass = `w-full px-3 py-2 rounded-lg border transition-colors ${
        darkMode
            ? 'bg-[#282828] border-[#383838] text-white focus:border-[#1DB954]'
            : 'bg-white border-slate-300 text-slate-900 focus:border-cyan-500'
    } focus:outline-none focus:ring-2 focus:ring-opacity-30 ${
        darkMode ? 'focus:ring-[#1DB954]' : 'focus:ring-cyan-500'
    }`;

    const labelClass = `block text-sm font-medium mb-1 ${
        darkMode ? 'text-[#b3b3b3]' : 'text-slate-600'
    }`;

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                        onClick={onClose}
                    />

                    {/* Modal */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className={`relative w-full max-w-lg rounded-xl shadow-2xl overflow-hidden ${
                            darkMode ? 'bg-[#181818]' : 'bg-white'
                        }`}
                    >
                        {/* Header */}
                        <div className={`flex items-center justify-between px-6 py-4 border-b ${
                            darkMode ? 'border-[#282828]' : 'border-slate-200'
                        }`}>
                            <div className="flex items-center gap-3">
                                <Settings2 className={`w-5 h-5 ${darkMode ? 'text-[#1DB954]' : 'text-cyan-500'}`} />
                                <h2 className={`text-lg font-semibold ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                                    Settings
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
                        <div className="px-6 py-4 max-h-[70vh] overflow-y-auto">
                            {/* GPU Hardware Section */}
                            <div className="mb-6">
                                <h3 className={`flex items-center gap-2 text-sm font-semibold uppercase tracking-wide mb-3 ${
                                    darkMode ? 'text-white' : 'text-slate-900'
                                }`}>
                                    <Cpu className="w-4 h-4" />
                                    GPU Hardware
                                </h3>
                                <div className={`p-4 rounded-lg ${
                                    darkMode ? 'bg-[#282828]' : 'bg-slate-50'
                                }`}>
                                    {!gpuStatus?.cuda_available ? (
                                        <p className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-600'}>
                                            No CUDA GPU detected
                                        </p>
                                    ) : (
                                        <div className="space-y-2">
                                            {gpuStatus.gpus.map((gpu) => (
                                                <div key={gpu.index} className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className={`font-medium ${
                                                            darkMode ? 'text-white' : 'text-slate-900'
                                                        }`}>
                                                            GPU {gpu.index}:
                                                        </span>
                                                        <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-600'}>
                                                            {gpu.name}
                                                        </span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className={`text-sm px-2 py-0.5 rounded ${
                                                            darkMode ? 'bg-[#383838] text-[#b3b3b3]' : 'bg-slate-200 text-slate-600'
                                                        }`}>
                                                            {gpu.vram_gb} GB
                                                        </span>
                                                        {gpu.supports_flash_attention && (
                                                            <span className={`text-xs px-2 py-0.5 rounded ${
                                                                darkMode ? 'bg-[#1DB954]/20 text-[#1DB954]' : 'bg-cyan-100 text-cyan-700'
                                                            }`}>
                                                                Flash OK
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Configuration Section */}
                            <div className="mb-6">
                                <h3 className={`text-sm font-semibold uppercase tracking-wide mb-3 ${
                                    darkMode ? 'text-white' : 'text-slate-900'
                                }`}>
                                    Configuration
                                </h3>
                                <div className="space-y-4">
                                    {/* 4-bit Quantization */}
                                    <div>
                                        <label className={labelClass}>4-bit Quantization</label>
                                        <select
                                            value={settings.quantization_4bit}
                                            onChange={(e) => {
                                                const newValue = e.target.value;
                                                if (newValue !== 'false' && settings.torch_compile) {
                                                    // Enabling 4-bit - disable torch.compile
                                                    setSettings({
                                                        ...settings,
                                                        quantization_4bit: newValue,
                                                        torch_compile: false
                                                    });
                                                } else {
                                                    setSettings({ ...settings, quantization_4bit: newValue });
                                                }
                                            }}
                                            className={selectClass}
                                        >
                                            <option value="auto">Auto (based on VRAM)</option>
                                            <option value="true">Enabled</option>
                                            <option value="false">Disabled (required for torch.compile)</option>
                                        </select>
                                        <p className={`text-xs mt-1 ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                            Reduces VRAM usage from ~11GB to ~3GB
                                        </p>
                                    </div>

                                    {/* Sequential Offload / Memory Swap Mode */}
                                    <div>
                                        <label className={labelClass}>Memory Swap Mode</label>
                                        <select
                                            value={settings.sequential_offload}
                                            onChange={(e) => setSettings({ ...settings, sequential_offload: e.target.value })}
                                            className={selectClass}
                                        >
                                            <option value="auto">Auto (based on VRAM)</option>
                                            <option value="true">Force Enabled (recommended if getting CUBLAS errors)</option>
                                            <option value="false">Disabled</option>
                                        </select>
                                        <p className={`text-xs mt-1 ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                            Loads one model at a time to reduce VRAM usage. Enable if you see CUBLAS_STATUS_EXECUTION_FAILED errors.
                                        </p>
                                    </div>

                                    {/* mmgp INT8 Quantization */}
                                    <div>
                                        <div className="flex items-center justify-between">
                                            <label className={labelClass}>INT8 Quantization (mmgp)</label>
                                            <button
                                                onClick={() => {
                                                    const newValue = settings.mmgp_quantization === 'true' ? 'false' : 'true';
                                                    setSettings({ ...settings, mmgp_quantization: newValue });
                                                }}
                                                className={`relative w-11 h-6 rounded-full transition-colors ${
                                                    settings.mmgp_quantization === 'true'
                                                        ? darkMode ? 'bg-[#1DB954]' : 'bg-cyan-500'
                                                        : darkMode ? 'bg-[#383838]' : 'bg-slate-300'
                                                }`}
                                            >
                                                <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                                                    settings.mmgp_quantization === 'true' ? 'translate-x-5' : ''
                                                }`} />
                                            </button>
                                        </div>
                                        <p className={`text-xs mt-1 ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                            {settings.mmgp_quantization === 'true'
                                                ? 'INT8: Lower VRAM usage, ~12% slower generation'
                                                : 'bf16: Faster generation (recommended for RTX 3060+)'}
                                        </p>
                                    </div>

                                    {/* torch.compile */}
                                    <div>
                                        <div className="flex items-center justify-between">
                                            <label className={labelClass}>torch.compile</label>
                                            <button
                                                onClick={() => {
                                                    const newCompile = !settings.torch_compile;
                                                    if (newCompile) {
                                                        // Enabling torch.compile - disable 4-bit quantization
                                                        setSettings({
                                                            ...settings,
                                                            torch_compile: true,
                                                            quantization_4bit: 'false'
                                                        });
                                                    } else {
                                                        setSettings({ ...settings, torch_compile: false });
                                                    }
                                                }}
                                                className={`relative w-11 h-6 rounded-full transition-colors ${
                                                    settings.torch_compile
                                                        ? darkMode ? 'bg-[#1DB954]' : 'bg-cyan-500'
                                                        : darkMode ? 'bg-[#383838]' : 'bg-slate-300'
                                                }`}
                                            >
                                                <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                                                    settings.torch_compile ? 'translate-x-5' : ''
                                                }`} />
                                            </button>
                                        </div>
                                        <p className={`text-xs mt-1 ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                            ~2x faster inference (requires full precision)
                                        </p>
                                        {settings.torch_compile && (
                                            <>
                                                {/* Warning for older GPUs */}
                                                {gpuStatus?.gpus && Object.values(gpuStatus.gpus).some(
                                                    (gpu: { compute_capability?: number }) => gpu.compute_capability && gpu.compute_capability < 7.5
                                                ) && (
                                                    <div className={`mt-2 p-2 rounded text-xs ${
                                                        darkMode ? 'bg-amber-900/30 text-amber-400' : 'bg-amber-50 text-amber-700'
                                                    }`}>
                                                        <strong>⚠ Warning:</strong> Your GPU (SM {
                                                            Object.values(gpuStatus.gpus).find(
                                                                (gpu: { compute_capability?: number }) => gpu.compute_capability && gpu.compute_capability < 7.5
                                                            )?.compute_capability
                                                        }) is older than recommended for torch.compile.
                                                        torch.compile works best on Turing (SM 7.5+) or newer GPUs (RTX 20xx/30xx/40xx, A100, etc.).
                                                        On older GPUs, compilation may be very slow or fail. The backend will auto-disable it for stability.
                                                    </div>
                                                )}
                                                <div className={`mt-2 p-2 rounded text-xs ${
                                                    darkMode ? 'bg-blue-900/20 text-blue-400' : 'bg-blue-50 text-blue-700'
                                                }`}>
                                                    <strong>Note:</strong> 4-bit quantization has been disabled for torch.compile compatibility.
                                                    First generation will take 5-10 minutes to compile. Subsequent runs will be ~2x faster.
                                                    Requires ~11GB VRAM without quantization.
                                                </div>
                                            </>
                                        )}
                                    </div>

                                    {/* torch.compile mode */}
                                    {settings.torch_compile && (
                                        <div>
                                            <label className={labelClass}>Compile Mode</label>
                                            <select
                                                value={settings.torch_compile_mode}
                                                onChange={(e) => setSettings({ ...settings, torch_compile_mode: e.target.value })}
                                                className={selectClass}
                                            >
                                                <option value="default">Default</option>
                                                <option value="reduce-overhead">Reduce Overhead</option>
                                                <option value="max-autotune">Max Autotune</option>
                                            </select>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* LLM Provider Section */}
                            <div className="mb-6">
                                <h3 className={`flex items-center gap-2 text-sm font-semibold uppercase tracking-wide mb-3 ${
                                    darkMode ? 'text-white' : 'text-slate-900'
                                }`}>
                                    <Globe className="w-4 h-4" />
                                    LLM Providers
                                    <span className={`text-xs font-normal ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                        ({providers.length})
                                    </span>
                                </h3>
                                <p className={`text-xs mb-4 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                    Add OpenAI, OpenRouter, Ollama, or any OpenAI-compatible API. Fetch models and enable the ones you want to use.
                                </p>
                                <div className="space-y-3">
                                    {/* Provider Cards */}
                                    {providers.map((provider) => {
                                        const isExpanded = expandedProvider === provider.id;
                                        const enabledCount = provider.enabled_models?.length || 0;
                                        const isFetching = fetchingModels === provider.id;

                                        return (
                                            <div key={provider.id} className={`rounded-lg border transition-colors ${
                                                darkMode ? 'border-[#383838] bg-[#1a1a1a]' : 'border-slate-200 bg-slate-50'
                                            }`}>
                                                {/* Provider Header */}
                                                <div
                                                    className={`flex items-center justify-between p-3 cursor-pointer hover:opacity-80`}
                                                    onClick={() => setExpandedProvider(isExpanded ? null : provider.id)}
                                                >
                                                    <div className="flex items-center gap-2 min-w-0">
                                                        <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${
                                                            provider.type === 'ollama'
                                                                ? 'bg-purple-500/20 text-purple-400'
                                                                : 'bg-blue-500/20 text-blue-400'
                                                        }`}>
                                                            {provider.type === 'ollama' ? 'Ollama' : 'OpenAI'}
                                                        </span>
                                                        <span className={`text-sm font-medium truncate ${darkMode ? 'text-white' : 'text-slate-800'}`}>
                                                            {provider.name}
                                                        </span>
                                                        {enabledCount > 0 && (
                                                            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                                                                darkMode ? 'bg-[#1DB954]/20 text-[#1DB954]' : 'bg-green-100 text-green-700'
                                                            }`}>
                                                                {enabledCount} active
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-1.5">
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); handleUpdateProvider(provider.id, { enabled: !provider.enabled }); }}
                                                            className={`p-1 rounded transition-colors ${provider.enabled
                                                                ? darkMode ? 'text-[#1DB954] hover:bg-[#282828]' : 'text-green-600 hover:bg-green-50'
                                                                : darkMode ? 'text-[#6a6a6a] hover:bg-[#282828]' : 'text-slate-400 hover:bg-slate-50'
                                                            }`}
                                                            title={provider.enabled ? 'Disable provider' : 'Enable provider'}
                                                        >
                                                            {provider.enabled ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                                                        </button>
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); handleDeleteProvider(provider.id); }}
                                                            className={`p-1 rounded transition-colors ${darkMode ? 'hover:bg-red-900/30 text-[#6a6a6a] hover:text-red-400' : 'hover:bg-red-50 text-slate-400 hover:text-red-500'}`}
                                                            title="Delete provider"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </button>
                                                        {isExpanded ? <ChevronUp className="w-4 h-4 text-[#6a6a6a]" /> : <ChevronDown className="w-4 h-4 text-[#6a6a6a]" />}
                                                    </div>
                                                </div>

                                                {/* Expanded Content */}
                                                {isExpanded && (
                                                    <div className={`px-3 pb-3 space-y-3 border-t ${darkMode ? 'border-[#282828]' : 'border-slate-200'}`}>
                                                        {/* URL display */}
                                                        <div className={`text-xs pt-2 font-mono truncate ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                                            {provider.base_url}
                                                        </div>

                                                        {/* API Key indicator */}
                                                        {provider.api_key && (
                                                            <div className={`flex items-center gap-1.5 text-xs ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                                                <Key className="w-3 h-3" />
                                                                <span>API Key: {provider.api_key}</span>
                                                            </div>
                                                        )}

                                                        {/* Fetch Models Button */}
                                                        <button
                                                            onClick={() => handleFetchModels(provider.id)}
                                                            disabled={isFetching}
                                                            className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                                                                darkMode
                                                                    ? 'bg-[#282828] text-white hover:bg-[#383838] border border-[#404040]'
                                                                    : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-300'
                                                            } disabled:opacity-50`}
                                                        >
                                                            {isFetching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                                                            {isFetching ? 'Fetching models...' : `Fetch Models (${provider.models?.length || 0} found)`}
                                                        </button>

                                                        {/* Model List with Checkboxes */}
                                                        {provider.models && provider.models.length > 0 && (
                                                            <div className={`max-h-48 overflow-y-auto rounded-lg border ${
                                                                darkMode ? 'border-[#282828] bg-[#0d0d0d]' : 'border-slate-200 bg-white'
                                                            }`}>
                                                                {provider.models.map((model) => {
                                                                    const isEnabled = provider.enabled_models?.includes(model.id) || false;
                                                                    return (
                                                                        <label
                                                                            key={model.id}
                                                                            className={`flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors ${
                                                                                darkMode
                                                                                    ? 'hover:bg-[#1a1a1a] border-b border-[#1a1a1a] last:border-b-0'
                                                                                    : 'hover:bg-slate-50 border-b border-slate-100 last:border-b-0'
                                                                            }`}
                                                                        >
                                                                            <input
                                                                                type="checkbox"
                                                                                checked={isEnabled}
                                                                                onChange={() => handleToggleModel(provider.id, model.id, !isEnabled)}
                                                                                className={`rounded border ${
                                                                                    darkMode
                                                                                        ? 'border-[#404040] bg-[#282828] text-[#1DB954] focus:ring-[#1DB954]'
                                                                                        : 'border-slate-300 text-cyan-500 focus:ring-cyan-500'
                                                                                }`}
                                                                            />
                                                                            <span className={`text-xs truncate ${
                                                                                isEnabled
                                                                                    ? darkMode ? 'text-white' : 'text-slate-800'
                                                                                    : darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'
                                                                            }`}>
                                                                                {model.name || model.id}
                                                                            </span>
                                                                        </label>
                                                                    );
                                                                })}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}

                                    {/* Add Provider */}
                                    {showAddProvider ? (
                                        <div className={`rounded-lg border p-3 space-y-3 ${
                                            darkMode ? 'border-[#1DB954]/30 bg-[#1a1a1a]' : 'border-cyan-300 bg-cyan-50/30'
                                        }`}>
                                            <div className="flex items-center gap-2 mb-1">
                                                <Plus className={`w-4 h-4 ${darkMode ? 'text-[#1DB954]' : 'text-cyan-500'}`} />
                                                <span className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-slate-800'}`}>Add Provider</span>
                                            </div>

                                            {/* Type selector */}
                                            <div className="flex gap-2">
                                                {(['openai', 'ollama'] as const).map((t) => (
                                                    <button
                                                        key={t}
                                                        onClick={() => {
                                                            setNewProviderType(t);
                                                            if (t === 'ollama' && !newProviderUrl) {
                                                                setNewProviderUrl('http://host.docker.internal:11434');
                                                                setNewProviderName('Ollama');
                                                            }
                                                        }}
                                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                                            newProviderType === t
                                                                ? darkMode ? 'bg-[#1DB954] text-black' : 'bg-cyan-500 text-white'
                                                                : darkMode ? 'bg-[#282828] text-[#b3b3b3]' : 'bg-slate-100 text-slate-600'
                                                        }`}
                                                    >
                                                        {t === 'openai' ? 'OpenAI Compatible' : 'Ollama'}
                                                    </button>
                                                ))}
                                            </div>

                                            {/* Name */}
                                            <input
                                                type="text"
                                                value={newProviderName}
                                                onChange={(e) => setNewProviderName(e.target.value)}
                                                placeholder="Provider name (e.g. OpenAI, OpenRouter)"
                                                className={selectClass}
                                            />

                                            {/* Base URL */}
                                            <input
                                                type="text"
                                                value={newProviderUrl}
                                                onChange={(e) => setNewProviderUrl(e.target.value)}
                                                placeholder={newProviderType === 'ollama' ? 'http://host.docker.internal:11434' : 'https://api.openai.com/v1'}
                                                className={selectClass}
                                            />

                                            {/* API Key */}
                                            {newProviderType === 'openai' && (
                                                <input
                                                    type="password"
                                                    value={newProviderKey}
                                                    onChange={(e) => setNewProviderKey(e.target.value)}
                                                    placeholder="API Key (required for most providers)"
                                                    className={selectClass}
                                                />
                                            )}

                                            <div className="flex gap-2">
                                                <button
                                                    onClick={handleAddProvider}
                                                    disabled={!newProviderUrl}
                                                    className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                                                        darkMode
                                                            ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                                            : 'bg-cyan-500 text-white hover:bg-cyan-600'
                                                    }`}
                                                >
                                                    Add Provider
                                                </button>
                                                <button
                                                    onClick={() => { setShowAddProvider(false); setNewProviderName(''); setNewProviderUrl(''); setNewProviderKey(''); }}
                                                    className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                                                        darkMode ? 'bg-[#282828] text-[#b3b3b3] hover:bg-[#383838]' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                                    }`}
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => setShowAddProvider(true)}
                                            className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors border border-dashed ${
                                                darkMode
                                                    ? 'border-[#383838] text-[#b3b3b3] hover:border-[#1DB954] hover:text-[#1DB954]'
                                                    : 'border-slate-300 text-slate-500 hover:border-cyan-400 hover:text-cyan-600'
                                            }`}
                                        >
                                            <Plus className="w-4 h-4" />
                                            Add LLM Provider
                                        </button>
                                    )}

                                    <p className={`text-xs ${darkMode ? 'text-[#6a6a6a]' : 'text-slate-400'}`}>
                                        After adding a provider, click "Fetch Models" to see available models, then check the ones you want to use.
                                    </p>
                                </div>
                            </div>

                            {/* Warning */}
                            {hasChanges && (
                                <div className={`flex items-start gap-3 p-4 rounded-lg mb-4 ${
                                    darkMode ? 'bg-amber-900/20 border border-amber-800' : 'bg-amber-50 border border-amber-200'
                                }`}>
                                    <AlertTriangle className={`w-5 h-5 flex-shrink-0 ${
                                        darkMode ? 'text-amber-400' : 'text-amber-600'
                                    }`} />
                                    <div>
                                        <p className={`text-sm font-medium ${
                                            darkMode ? 'text-amber-400' : 'text-amber-800'
                                        }`}>
                                            Changes require model reload
                                        </p>
                                        <p className={`text-xs mt-1 ${
                                            darkMode ? 'text-amber-400/70' : 'text-amber-700'
                                        }`}>
                                            This will take 1-3 minutes. No generation during reload.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Reload Progress */}
                            {isCurrentlyReloading && (
                                <div className={`p-4 rounded-lg mb-4 ${
                                    darkMode ? 'bg-[#282828]' : 'bg-slate-100'
                                }`}>
                                    <div className="flex items-center gap-3 mb-2">
                                        <RefreshCw className={`w-4 h-4 animate-spin ${
                                            darkMode ? 'text-[#1DB954]' : 'text-cyan-500'
                                        }`} />
                                        <span className={`text-sm font-medium ${
                                            darkMode ? 'text-white' : 'text-slate-900'
                                        }`}>
                                            {startupStatus?.message || 'Reloading...'}
                                        </span>
                                    </div>
                                    <div className={`w-full h-2 rounded-full overflow-hidden ${
                                        darkMode ? 'bg-[#383838]' : 'bg-slate-200'
                                    }`}>
                                        <div
                                            className={`h-full rounded-full transition-all duration-300 ${
                                                darkMode ? 'bg-[#1DB954]' : 'bg-cyan-500'
                                            }`}
                                            style={{ width: `${startupStatus?.progress || 0}%` }}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* HeartTranscriptor Section */}
                            <TranscriptorSettingsSection darkMode={darkMode} />

                            {/* Vertex AI (Video Generation) Section */}
                            <VertexAISettingsSection darkMode={darkMode} />
                        </div>

                        {/* Footer */}
                        <div className={`flex items-center justify-end gap-3 px-6 py-4 border-t ${
                            darkMode ? 'border-[#282828]' : 'border-slate-200'
                        }`}>
                            {saveSuccess && (
                                <span className={`flex items-center gap-1 text-sm ${
                                    darkMode ? 'text-[#1DB954]' : 'text-cyan-600'
                                }`}>
                                    <Check className="w-4 h-4" />
                                    Saved
                                </span>
                            )}
                            <button
                                onClick={handleSave}
                                disabled={isSaving || !hasChanges || isCurrentlyReloading}
                                className={`px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                                    darkMode
                                        ? 'bg-[#282828] text-white hover:bg-[#383838]'
                                        : 'bg-slate-100 text-slate-900 hover:bg-slate-200'
                                }`}
                            >
                                {isSaving ? 'Saving...' : 'Save'}
                            </button>
                            <button
                                onClick={handleReload}
                                disabled={isReloading || isCurrentlyReloading}
                                className={`px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 ${
                                    darkMode
                                        ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                        : 'bg-cyan-500 text-white hover:bg-cyan-600'
                                }`}
                            >
                                {(isReloading || isCurrentlyReloading) ? (
                                    <>
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                        Reloading...
                                    </>
                                ) : (
                                    <>
                                        <RefreshCw className="w-4 h-4" />
                                        Apply & Reload
                                    </>
                                )}
                            </button>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
}


// ============== HeartTranscriptor Settings Sub-Component ==============

function TranscriptorSettingsSection({ darkMode }: { darkMode: boolean }) {
    const [status, setStatus] = useState<TranscriptorStatus | null>(null);
    const [isDownloading, setIsDownloading] = useState(false);
    const [isLoadingModel, setIsLoadingModel] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        api.getTranscriptorStatus().then(setStatus).catch(() => {});
    }, []);

    const refreshStatus = async () => {
        try {
            const s = await api.getTranscriptorStatus();
            setStatus(s);
        } catch {}
    };

    const handleDownload = async () => {
        setIsDownloading(true);
        setMessage(null);
        try {
            const res = await api.downloadTranscriptor();
            setMessage(res.message);
            // Poll for completion
            const poll = setInterval(async () => {
                const s = await api.getTranscriptorStatus();
                setStatus(s);
                if (s.model_downloaded) {
                    clearInterval(poll);
                    setIsDownloading(false);
                    setMessage('HeartTranscriptor downloaded successfully!');
                }
            }, 3000);
            // Timeout after 10 min
            setTimeout(() => { clearInterval(poll); setIsDownloading(false); }, 600000);
        } catch (err: any) {
            setMessage(err?.response?.data?.detail || 'Download failed');
            setIsDownloading(false);
        }
    };

    const handleLoad = async () => {
        setIsLoadingModel(true);
        setMessage(null);
        try {
            const res = await api.loadTranscriptor();
            setMessage(res.message);
            await refreshStatus();
        } catch (err: any) {
            setMessage(err?.response?.data?.detail || 'Load failed');
        } finally {
            setIsLoadingModel(false);
        }
    };

    const handleUnload = async () => {
        try {
            const res = await api.unloadTranscriptor();
            setMessage(res.message);
            await refreshStatus();
        } catch (err: any) {
            setMessage(err?.response?.data?.detail || 'Unload failed');
        }
    };

    if (!status) return null;

    return (
        <div className={`mt-6 pt-6 border-t ${darkMode ? 'border-[#282828]' : 'border-slate-200'}`}>
            <div className="flex items-center gap-2 mb-4">
                <Mic className={`w-5 h-5 ${darkMode ? 'text-[#1DB954]' : 'text-cyan-500'}`} />
                <h3 className={`text-sm font-semibold ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                    HeartTranscriptor (Lyrics Extraction)
                </h3>
            </div>

            <div className={`rounded-lg p-4 space-y-3 ${darkMode ? 'bg-[#282828]' : 'bg-slate-50'}`}>
                {/* Status indicators */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                        <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>Pipeline</span>
                        <span className={`flex items-center gap-1 ${status.available ? (darkMode ? 'text-[#1DB954]' : 'text-green-600') : (darkMode ? 'text-red-400' : 'text-red-500')}`}>
                            {status.available ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                            {status.available ? 'Available' : 'Not installed'}
                        </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                        <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>Model (~1.5GB)</span>
                        <span className={`flex items-center gap-1 ${status.model_downloaded ? (darkMode ? 'text-[#1DB954]' : 'text-green-600') : (darkMode ? 'text-[#b3b3b3]' : 'text-slate-400')}`}>
                            {status.model_downloaded ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                            {status.model_downloaded ? 'Downloaded' : 'Not downloaded'}
                        </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                        <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>GPU Status</span>
                        <span className={`flex items-center gap-1 ${status.model_loaded ? (darkMode ? 'text-[#1DB954]' : 'text-green-600') : (darkMode ? 'text-[#b3b3b3]' : 'text-slate-400')}`}>
                            {status.model_loaded ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                            {status.model_loaded ? 'Loaded' : 'Not loaded'}
                        </span>
                    </div>
                    {status.demucs_available && (
                        <div className="flex items-center justify-between text-sm">
                            <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>Vocal Separation</span>
                            <span className={`flex items-center gap-1 ${darkMode ? 'text-[#1DB954]' : 'text-green-600'}`}>
                                <CheckCircle className="w-3.5 h-3.5" />
                                demucs ready
                            </span>
                        </div>
                    )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2 pt-2">
                    {!status.model_downloaded && (
                        <button
                            onClick={handleDownload}
                            disabled={isDownloading || !status.available}
                            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                                darkMode
                                    ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                    : 'bg-cyan-500 text-white hover:bg-cyan-600'
                            }`}
                        >
                            {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                            {isDownloading ? 'Downloading...' : 'Download Model'}
                        </button>
                    )}
                    {status.model_downloaded && !status.model_loaded && (
                        <button
                            onClick={handleLoad}
                            disabled={isLoadingModel}
                            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                                darkMode
                                    ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                    : 'bg-cyan-500 text-white hover:bg-cyan-600'
                            }`}
                        >
                            {isLoadingModel ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mic className="w-4 h-4" />}
                            {isLoadingModel ? 'Loading...' : 'Load to GPU'}
                        </button>
                    )}
                    {status.model_loaded && (
                        <button
                            onClick={handleUnload}
                            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                darkMode
                                    ? 'bg-[#282828] text-[#b3b3b3] hover:bg-[#383838] border border-[#404040]'
                                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-200'
                            }`}
                        >
                            <Trash2 className="w-4 h-4" />
                            Unload from GPU
                        </button>
                    )}
                </div>

                {/* Status message */}
                {message && (
                    <p className={`text-xs mt-2 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                        {message}
                    </p>
                )}
            </div>

            <p className={`text-xs mt-2 ${darkMode ? 'text-[#666]' : 'text-slate-400'}`}>
                HeartTranscriptor extracts lyrics from audio using AI. The model uses ~1.5GB VRAM when loaded.
                You can unload it after use to free GPU memory for music generation.
            </p>
        </div>
    );
}


// ============== Vertex AI (Video Generation) Settings Sub-Component ==============

function VertexAISettingsSection({ darkMode }: { darkMode: boolean }) {
    const [status, setStatus] = useState<VertexAIStatus | null>(null);
    const [projectId, setProjectId] = useState('');
    const [location, setLocation] = useState('us-central1');
    const [jsonContent, setJsonContent] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

    useEffect(() => {
        api.getVertexAIStatus().then((s) => {
            setStatus(s);
            if (s.project_id) setProjectId(s.project_id);
            if (s.location) setLocation(s.location);
        }).catch(() => {});
    }, []);

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            const content = ev.target?.result as string;
            setJsonContent(content);
            // Auto-extract project_id from service account JSON
            try {
                const parsed = JSON.parse(content);
                if (parsed.project_id) setProjectId(parsed.project_id);
            } catch {}
        };
        reader.readAsText(file);
    };

    const handleSave = async () => {
        if (!jsonContent || !projectId) {
            setMessage({ text: 'Service Account JSON and Project ID are required', type: 'error' });
            return;
        }
        setIsSaving(true);
        setMessage(null);
        try {
            await api.configureVertexAI(jsonContent, projectId, location);
            const s = await api.getVertexAIStatus();
            setStatus(s);
            setMessage({ text: 'Vertex AI configured successfully!', type: 'success' });
        } catch (err: any) {
            setMessage({ text: err?.response?.data?.detail || 'Configuration failed', type: 'error' });
        } finally {
            setIsSaving(false);
        }
    };

    const handleRemove = async () => {
        try {
            await api.removeVertexAI();
            setStatus({ configured: false });
            setJsonContent('');
            setProjectId('');
            setMessage({ text: 'Vertex AI credentials removed', type: 'success' });
        } catch (err: any) {
            setMessage({ text: err?.response?.data?.detail || 'Failed to remove', type: 'error' });
        }
    };

    const inputClass = `w-full px-3 py-2 rounded-lg text-sm ${
        darkMode
            ? 'bg-[#1a1a1a] border border-[#333] text-white placeholder-[#666]'
            : 'bg-white border border-slate-200 text-slate-900 placeholder-slate-400'
    }`;

    return (
        <div className={`mt-6 pt-6 border-t ${darkMode ? 'border-[#282828]' : 'border-slate-200'}`}>
            <div className="flex items-center gap-2 mb-4">
                <Video className={`w-5 h-5 ${darkMode ? 'text-[#1DB954]' : 'text-cyan-500'}`} />
                <h3 className={`text-sm font-semibold ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                    Vertex AI (Video Generation)
                </h3>
                {status?.configured && (
                    <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                        darkMode ? 'bg-[#1DB954]/20 text-[#1DB954]' : 'bg-green-100 text-green-700'
                    }`}>
                        Connected
                    </span>
                )}
            </div>

            <div className={`rounded-lg p-4 space-y-3 ${darkMode ? 'bg-[#282828]' : 'bg-slate-50'}`}>
                {/* Status */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                        <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>Status</span>
                        <span className={`flex items-center gap-1 ${
                            status?.configured
                                ? (darkMode ? 'text-[#1DB954]' : 'text-green-600')
                                : (darkMode ? 'text-[#b3b3b3]' : 'text-slate-400')
                        }`}>
                            {status?.configured ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                            {status?.configured ? 'Configured' : 'Not configured'}
                        </span>
                    </div>
                    {status?.configured && status.project_id && (
                        <div className="flex items-center justify-between text-sm">
                            <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>Project</span>
                            <span className={darkMode ? 'text-white' : 'text-slate-800'}>{status.project_id}</span>
                        </div>
                    )}
                    {status?.configured && status.location && (
                        <div className="flex items-center justify-between text-sm">
                            <span className={darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}>Region</span>
                            <span className={darkMode ? 'text-white' : 'text-slate-800'}>{status.location}</span>
                        </div>
                    )}
                </div>

                {/* Configuration form */}
                {!status?.configured && (
                    <div className="space-y-3 pt-2">
                        {/* Service Account JSON upload */}
                        <div>
                            <label className={`block text-xs mb-1 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                Service Account JSON
                            </label>
                            <label className={`flex items-center justify-center gap-2 px-3 py-3 rounded-lg cursor-pointer border border-dashed transition-colors ${
                                darkMode
                                    ? 'border-[#404040] hover:border-[#1DB954] text-[#b3b3b3] hover:text-[#1DB954]'
                                    : 'border-slate-300 hover:border-cyan-400 text-slate-500 hover:text-cyan-600'
                            }`}>
                                <Upload className="w-4 h-4" />
                                <span className="text-sm">{jsonContent ? 'JSON loaded' : 'Upload JSON file'}</span>
                                <input type="file" accept=".json" onChange={handleFileUpload} className="hidden" />
                            </label>
                            {jsonContent && (
                                <p className={`text-xs mt-1 flex items-center gap-1 ${darkMode ? 'text-[#1DB954]' : 'text-green-600'}`}>
                                    <CheckCircle className="w-3 h-3" /> JSON file loaded
                                </p>
                            )}
                        </div>

                        {/* Project ID */}
                        <div>
                            <label className={`block text-xs mb-1 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                GCP Project ID
                            </label>
                            <input
                                type="text"
                                value={projectId}
                                onChange={(e) => setProjectId(e.target.value)}
                                placeholder="my-project-id"
                                className={inputClass}
                            />
                        </div>

                        {/* Location */}
                        <div>
                            <label className={`block text-xs mb-1 ${darkMode ? 'text-[#b3b3b3]' : 'text-slate-500'}`}>
                                Region
                            </label>
                            <select
                                value={location}
                                onChange={(e) => setLocation(e.target.value)}
                                className={inputClass}
                            >
                                <option value="us-central1">us-central1</option>
                                <option value="us-east4">us-east4</option>
                                <option value="us-west1">us-west1</option>
                                <option value="europe-west4">europe-west4</option>
                                <option value="asia-northeast1">asia-northeast1</option>
                            </select>
                        </div>

                        <button
                            onClick={handleSave}
                            disabled={isSaving || !jsonContent || !projectId}
                            className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                                darkMode
                                    ? 'bg-[#1DB954] text-black hover:bg-[#1ed760]'
                                    : 'bg-cyan-500 text-white hover:bg-cyan-600'
                            }`}
                        >
                            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
                            {isSaving ? 'Configuring...' : 'Configure Vertex AI'}
                        </button>
                    </div>
                )}

                {/* Remove button (when configured) */}
                {status?.configured && (
                    <div className="pt-2">
                        <button
                            onClick={handleRemove}
                            className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                darkMode
                                    ? 'bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-800/50'
                                    : 'bg-red-50 text-red-600 hover:bg-red-100 border border-red-200'
                            }`}
                        >
                            <Trash2 className="w-4 h-4" />
                            Remove Credentials
                        </button>
                    </div>
                )}

                {/* Message */}
                {message && (
                    <p className={`text-xs ${
                        message.type === 'success'
                            ? (darkMode ? 'text-[#1DB954]' : 'text-green-600')
                            : (darkMode ? 'text-red-400' : 'text-red-500')
                    }`}>
                        {message.text}
                    </p>
                )}
            </div>

            <p className={`text-xs mt-2 ${darkMode ? 'text-[#666]' : 'text-slate-400'}`}>
                Vertex AI uses Google Gemini + Veo 3.1 to generate AI music videos. Upload a Google Cloud service account JSON with Vertex AI access.
            </p>
        </div>
    );
}
