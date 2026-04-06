import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, User, ArrowLeft, Loader2, CheckCircle, AlertCircle, Music, Lock } from 'lucide-react';

const EyeIcon = ({ open }: { open: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {open ? (
      <>
        <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />
        <circle cx="12" cy="12" r="3" />
      </>
    ) : (
      <>
        <path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" />
        <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" />
        <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" />
        <path d="m2 2 20 20" />
      </>
    )}
  </svg>
);

// --- Types ---
type AuthView = 'login' | 'register';
type LoginStep = 'email' | 'code';

interface LoginPageProps {
  onLogin: (token: string, user: { id: string; name: string; email: string; is_admin?: boolean }) => void;
}

// --- Floating Music Notes Background ---
const NOTES = ['\u266A', '\u266B', '\u266C', '\u266D', '\u266E', '\uD834\uDD1E'];

function FloatingNotes() {
  const notes = useMemo(() =>
    Array.from({ length: 18 }, (_, i) => ({
      id: i,
      char: NOTES[i % NOTES.length],
      x: Math.random() * 100,
      delay: Math.random() * 20,
      duration: 15 + Math.random() * 15,
      size: 14 + Math.random() * 20,
      opacity: 0.08 + Math.random() * 0.15,
    })), []);

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {notes.map((n) => (
        <div
          key={n.id}
          className="absolute animate-float-note"
          style={{
            left: `${n.x}%`,
            bottom: '-5%',
            fontSize: `${n.size}px`,
            color: '#22c55e',
            opacity: n.opacity,
            animationDuration: `${n.duration}s`,
            animationDelay: `${n.delay}s`,
          }}
        >
          {n.char}
        </div>
      ))}
    </div>
  );
}

// --- Pulsing Circles ---
function PulsingCircles() {
  const circles = useMemo(() =>
    Array.from({ length: 6 }, (_, i) => ({
      id: i,
      x: 10 + Math.random() * 80,
      y: 10 + Math.random() * 80,
      size: 80 + Math.random() * 200,
      delay: Math.random() * 5,
      duration: 5 + Math.random() * 4,
    })), []);

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {circles.map((c) => (
        <div
          key={c.id}
          className="absolute rounded-full animate-pulse-circle"
          style={{
            left: `${c.x}%`,
            top: `${c.y}%`,
            width: `${c.size}px`,
            height: `${c.size}px`,
            background: 'rgba(34, 197, 94, 0.06)',
            filter: 'blur(40px)',
            animationDuration: `${c.duration}s`,
            animationDelay: `${c.delay}s`,
          }}
        />
      ))}
    </div>
  );
}

// --- Sound Wave Canvas ---
function SoundWave() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    let phase = 0;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const waves = [
        { amp: 30, freq: 0.008, speed: 0.02, opacity: 0.12, y: canvas.height * 0.38 },
        { amp: 20, freq: 0.012, speed: -0.015, opacity: 0.08, y: canvas.height * 0.42 },
        { amp: 15, freq: 0.018, speed: 0.025, opacity: 0.06, y: canvas.height * 0.40 },
      ];

      waves.forEach((w) => {
        ctx.beginPath();
        ctx.strokeStyle = `rgba(34, 197, 94, ${w.opacity})`;
        ctx.lineWidth = 2;
        for (let x = 0; x < canvas.width; x++) {
          const y = w.y + Math.sin(x * w.freq + phase * w.speed * 60) * w.amp;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      });

      phase += 0.016;
      animRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

// --- Equalizer Bars ---
function EqualizerBars() {
  const bars = useMemo(() =>
    Array.from({ length: 50 }, (_, i) => ({
      id: i,
      maxHeight: 15 + Math.random() * 45,
      delay: Math.random() * 2,
      duration: 0.8 + Math.random() * 1.2,
    })), []);

  return (
    <div className="fixed bottom-0 left-0 right-0 h-16 flex items-end justify-center gap-[3px] pointer-events-none z-0 opacity-60">
      {bars.map((b) => (
        <div
          key={b.id}
          className="w-[2px] bg-green-500/10 rounded-t animate-equalizer"
          style={{
            animationDuration: `${b.duration}s`,
            animationDelay: `${b.delay}s`,
            '--max-h': `${b.maxHeight}px`,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}

// --- Code Input ---
function CodeInput({
  length,
  value,
  onChange,
  error,
  disabled,
}: {
  length: number;
  value: string;
  onChange: (val: string) => void;
  error: boolean;
  disabled: boolean;
}) {
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = value.split('').concat(Array(length - value.length).fill(''));

  const handleChange = (i: number, char: string) => {
    if (disabled) return;
    // Only allow digits
    const d = char.replace(/\D/g, '');
    if (!d) return;
    const newVal = digits.slice();
    newVal[i] = d[0];
    const joined = newVal.join('').slice(0, length);
    onChange(joined);
    if (i < length - 1) {
      inputRefs.current[i + 1]?.focus();
    }
  };

  const handleKeyDown = (i: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace') {
      e.preventDefault();
      const newVal = digits.slice();
      if (digits[i]) {
        newVal[i] = '';
        onChange(newVal.join(''));
      } else if (i > 0) {
        newVal[i - 1] = '';
        onChange(newVal.join(''));
        inputRefs.current[i - 1]?.focus();
      }
    } else if (e.key === 'ArrowLeft' && i > 0) {
      inputRefs.current[i - 1]?.focus();
    } else if (e.key === 'ArrowRight' && i < length - 1) {
      inputRefs.current[i + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    if (pasted) {
      onChange(pasted);
      const focusIdx = Math.min(pasted.length, length - 1);
      inputRefs.current[focusIdx]?.focus();
    }
  };

  return (
    <div className="flex gap-2 justify-center">
      {digits.slice(0, length).map((d, i) => (
        <motion.input
          key={i}
          ref={(el) => { inputRefs.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d}
          disabled={disabled}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          className={`
            w-10 h-12 sm:w-12 sm:h-14 text-center text-xl font-mono font-bold rounded-lg
            outline-none transition-all duration-200
            ${error
              ? 'border-2 border-red-500 bg-red-500/10 text-red-400 animate-shake'
              : d
                ? 'border-2 border-green-500 bg-green-500/10 text-green-400'
                : 'border-2 border-white/10 bg-white/[0.05] text-white/80'
            }
            focus:border-green-500 focus:bg-green-500/[0.08] focus:ring-2 focus:ring-green-500/20
            disabled:opacity-50
          `}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: i * 0.05, type: 'spring', stiffness: 400, damping: 25 }}
        />
      ))}
    </div>
  );
}

// --- Main Login Page ---
export function LoginPage({ onLogin }: LoginPageProps) {
  const [view, setView] = useState<AuthView>('login');
  const [loginStep, setLoginStep] = useState<LoginStep>('email');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [codeError, setCodeError] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [resendCooldown, setResendCooldown] = useState(0);

  const emailInputRef = useRef<HTMLInputElement>(null);

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0) return;
    const t = setInterval(() => setCountdown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, [countdown]);

  // Resend cooldown
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setInterval(() => setResendCooldown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, [resendCooldown]);

  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const maskEmail = (e: string) => {
    const [user, domain] = e.split('@');
    return `${user[0]}${'*'.repeat(Math.max(1, user.length - 2))}${user.slice(-1)}@${domain}`;
  };

  // API calls
  const apiBase = import.meta.env.DEV
    ? `http://${window.location.hostname}:8000`
    : `${window.location.protocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}`;

  const handleRegister = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Registration failed');
        return;
      }
      setSuccess('Registration submitted! Check your email after admin approval.');
      setTimeout(() => {
        setView('login');
        setSuccess('');
      }, 4000);
    } catch {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Invalid email or password');
        return;
      }
      // Password verified — now go to code step (2FA)
      setLoginStep('code');
      setCountdown(data.expires_in || 600);
      setResendCooldown(60);
      setCode('');
      setCodeError(false);
    } catch {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSendCode = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${apiBase}/auth/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Failed to send code');
        return;
      }
      setLoginStep('code');
      setCountdown(data.expires_in || 600);
      setResendCooldown(60);
      setCode('');
      setCodeError(false);
    } catch {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [apiBase, email]);

  const handleVerify = useCallback(async (codeVal?: string) => {
    const verifyCode = codeVal || code;
    if (verifyCode.length < 8) return;
    setLoading(true);
    setError('');
    setCodeError(false);
    try {
      const res = await fetch(`${apiBase}/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code: verifyCode }),
      });
      const data = await res.json();
      if (!res.ok) {
        setCodeError(true);
        setCode('');
        setError(data.detail || 'Invalid code');
        return;
      }
      onLogin(data.token, data.user);
    } catch {
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [apiBase, code, email, onLogin]);

  // Auto-verify when all 8 digits entered
  useEffect(() => {
    if (code.length === 8 && loginStep === 'code') {
      const timer = setTimeout(() => handleVerify(code), 300);
      return () => clearTimeout(timer);
    }
  }, [code, loginStep, handleVerify]);

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  const switchView = (v: AuthView) => {
    setView(v);
    setError('');
    setSuccess('');
    setLoginStep('email');
    setCode('');
    setPassword('');
    setCodeError(false);
  };

  return (
    <div className="h-screen bg-[#0f0f1a] flex items-center justify-center relative overflow-hidden">
      {/* Animated Background */}
      <FloatingNotes />
      <PulsingCircles />
      <SoundWave />
      <EqualizerBars />

      {/* Auth Card */}
      <motion.div
        className="relative z-10 w-full max-w-[440px] mx-4"
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ delay: 0.2, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="bg-[#1e1e32] border border-[#2e2e4a] rounded-2xl shadow-[0_0_60px_rgba(34,197,94,0.1),0_25px_50px_rgba(0,0,0,0.6)] p-8 sm:p-10">
          {/* Logo */}
          <motion.div
            className="text-center mb-8"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 mb-2">
              <motion.div
                animate={{ filter: ['drop-shadow(0 0 4px rgba(34,197,94,0.3))', 'drop-shadow(0 0 12px rgba(34,197,94,0.6))', 'drop-shadow(0 0 4px rgba(34,197,94,0.3))'] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <Music className="w-8 h-8 text-green-500" />
              </motion.div>
              <h1 className="text-2xl font-bold">
                <span className="text-green-500">Heart</span>
                <span className="text-white">MuLa</span>
              </h1>
            </div>
            <p className="text-sm text-white/40">AI Music Creation Studio</p>
          </motion.div>

          {/* Tab Switcher */}
          <div className="relative flex mb-8 bg-white/[0.04] rounded-lg p-1">
            <motion.div
              className="absolute top-1 bottom-1 rounded-md bg-green-500/20 border border-green-500/30"
              layout
              style={{ width: '50%', left: view === 'login' ? '0.25rem' : 'calc(50% - 0.25rem)' }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
            <button
              onClick={() => switchView('login')}
              className={`flex-1 py-2 text-sm font-medium rounded-md relative z-10 transition-colors ${view === 'login' ? 'text-green-400' : 'text-white/40 hover:text-white/60'}`}
            >
              Login
            </button>
            <button
              onClick={() => switchView('register')}
              className={`flex-1 py-2 text-sm font-medium rounded-md relative z-10 transition-colors ${view === 'register' ? 'text-green-400' : 'text-white/40 hover:text-white/60'}`}
            >
              Register
            </button>
          </div>

          {/* Error / Success Messages */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-6"
              >
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                <p className="text-sm text-red-400">{error}</p>
              </motion.div>
            )}
            {success && (
              <motion.div
                key="success"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="flex items-center gap-2 bg-green-500/10 border border-green-500/20 rounded-lg px-4 py-3 mb-6"
              >
                <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                <p className="text-sm text-green-400">{success}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form Content */}
          <AnimatePresence mode="wait">
            {view === 'login' && loginStep === 'email' && (
              <motion.div
                key="login-email"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                <label className="block text-sm text-white/50 mb-2">Email</label>
                <div className="relative mb-4">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    ref={emailInputRef}
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError(''); }}
                    onKeyDown={(e) => e.key === 'Enter' && isEmailValid && (password ? handlePasswordLogin() : handleSendCode())}
                    className="w-full bg-white/[0.08] border border-white/[0.15] rounded-lg pl-10 pr-4 py-3 text-white placeholder-white/30 outline-none transition-all focus:border-green-500 focus:ring-2 focus:ring-green-500/20"
                    autoFocus
                  />
                </div>

                {/* Password field (optional - for admin/password users) */}
                <label className="block text-sm text-white/50 mb-2">Password <span className="text-white/30">(admin only)</span></label>
                <div className="relative mb-6">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Leave empty for email code login"
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError(''); }}
                    onKeyDown={(e) => e.key === 'Enter' && isEmailValid && password && handlePasswordLogin()}
                    className="w-full bg-white/[0.08] border border-white/[0.15] rounded-lg pl-10 pr-10 py-3 text-white placeholder-white/30 outline-none transition-all focus:border-green-500 focus:ring-2 focus:ring-green-500/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                  >
                    <EyeIcon open={!showPassword} />
                  </button>
                </div>

                {password ? (
                  <button
                    onClick={handlePasswordLogin}
                    disabled={!isEmailValid || !password || loading}
                    className="w-full bg-green-500 hover:bg-green-600 active:bg-green-700 disabled:bg-green-500/30 disabled:cursor-not-allowed text-black font-semibold py-3 rounded-lg transition-all shadow-lg shadow-green-500/20 hover:shadow-green-500/30 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] flex items-center justify-center gap-2"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                    {loading ? 'Signing in...' : 'Sign In'}
                  </button>
                ) : (
                  <button
                    onClick={handleSendCode}
                    disabled={!isEmailValid || loading}
                    className="w-full bg-green-500 hover:bg-green-600 active:bg-green-700 disabled:bg-green-500/30 disabled:cursor-not-allowed text-black font-semibold py-3 rounded-lg transition-all shadow-lg shadow-green-500/20 hover:shadow-green-500/30 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] flex items-center justify-center gap-2"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                    {loading ? 'Sending...' : 'Send Code'}
                  </button>
                )}
              </motion.div>
            )}

            {view === 'login' && loginStep === 'code' && (
              <motion.div
                key="login-code"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                {/* Success banner */}
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  className="bg-green-500/10 border border-green-500/20 rounded-lg px-4 py-2 mb-6 flex items-center gap-2"
                >
                  <CheckCircle className="w-4 h-4 text-green-400" />
                  <span className="text-sm text-green-400">Code sent to {maskEmail(email)}</span>
                </motion.div>

                <label className="block text-sm text-white/50 mb-3 text-center">Verification Code</label>

                <div className="mb-4">
                  <CodeInput
                    length={8}
                    value={code}
                    onChange={(v) => { setCode(v); setCodeError(false); setError(''); }}
                    error={codeError}
                    disabled={loading}
                  />
                </div>

                {countdown > 0 && (
                  <p className="text-center text-xs text-white/30 mb-4">
                    Code expires in <span className="text-white/50 font-mono">{formatTime(countdown)}</span>
                  </p>
                )}

                <button
                  onClick={() => handleVerify()}
                  disabled={code.length < 8 || loading}
                  className="w-full bg-green-500 hover:bg-green-600 active:bg-green-700 disabled:bg-green-500/30 disabled:cursor-not-allowed text-black font-semibold py-3 rounded-lg transition-all shadow-lg shadow-green-500/20 flex items-center justify-center gap-2 mb-4"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {loading ? 'Verifying...' : 'Verify & Login'}
                </button>

                <div className="flex items-center justify-between text-xs">
                  <button
                    onClick={() => {
                      setLoginStep('email');
                      setCode('');
                      setError('');
                      setCodeError(false);
                    }}
                    className="text-white/40 hover:text-white/60 flex items-center gap-1 transition-colors"
                  >
                    <ArrowLeft className="w-3 h-3" /> Back to email
                  </button>
                  <button
                    onClick={handleSendCode}
                    disabled={resendCooldown > 0 || loading}
                    className="text-green-500 hover:text-green-400 disabled:text-white/20 disabled:cursor-not-allowed transition-colors"
                  >
                    {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Code'}
                  </button>
                </div>
              </motion.div>
            )}

            {view === 'register' && (
              <motion.div
                key="register"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                <label className="block text-sm text-white/50 mb-2">Display Name</label>
                <div className="relative mb-4">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="text"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => { setName(e.target.value); setError(''); }}
                    className="w-full bg-white/[0.08] border border-white/[0.15] rounded-lg pl-10 pr-4 py-3 text-white placeholder-white/30 outline-none transition-all focus:border-green-500 focus:ring-2 focus:ring-green-500/20"
                    autoFocus
                  />
                </div>

                <label className="block text-sm text-white/50 mb-2">Email</label>
                <div className="relative mb-6">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="email"
                    placeholder="your@email.com"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError(''); }}
                    onKeyDown={(e) => e.key === 'Enter' && isEmailValid && name.length >= 2 && handleRegister()}
                    className="w-full bg-white/[0.08] border border-white/[0.15] rounded-lg pl-10 pr-4 py-3 text-white placeholder-white/30 outline-none transition-all focus:border-green-500 focus:ring-2 focus:ring-green-500/20"
                  />
                </div>

                <button
                  onClick={handleRegister}
                  disabled={!isEmailValid || name.length < 2 || loading}
                  className="w-full bg-green-500 hover:bg-green-600 active:bg-green-700 disabled:bg-green-500/30 disabled:cursor-not-allowed text-black font-semibold py-3 rounded-lg transition-all shadow-lg shadow-green-500/20 hover:shadow-green-500/30 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] flex items-center justify-center gap-2"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {loading ? 'Creating...' : 'Create Account'}
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Footer Link */}
          <div className="mt-6 pt-6 border-t border-white/[0.06] text-center text-sm text-white/30">
            {view === 'login' ? (
              <>
                Don't have an account?{' '}
                <button onClick={() => switchView('register')} className="text-green-500 hover:text-green-400 transition-colors font-medium">
                  Register here
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button onClick={() => switchView('login')} className="text-green-500 hover:text-green-400 transition-colors font-medium">
                  Login here
                </button>
              </>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
