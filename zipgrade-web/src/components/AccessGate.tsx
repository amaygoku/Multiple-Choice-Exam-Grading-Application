import { useState } from 'react';
import { LockKeyhole, Eye, EyeOff, ShieldAlert } from 'lucide-react';

type AccessGateProps = {
  onUnlock: (password: string) => boolean;
};

export default function AccessGate({ onUnlock }: AccessGateProps) {
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = () => {
    setSubmitting(true);
    const ok = onUnlock(password);
    if (!ok) {
      setError('Wrong password. Please try again.');
      setSubmitting(false);
      return;
    }
    setError('');
  };

  return (
    <div className="min-h-[100dvh] bg-[#050816] text-white flex items-center justify-center px-4 py-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.18),transparent_35%),radial-gradient(circle_at_bottom,rgba(99,102,241,0.12),transparent_30%)]" />

      <div className="relative w-full max-w-md rounded-3xl border border-white/10 bg-[#0b1220]/95 shadow-2xl shadow-black/40 backdrop-blur-xl p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-cyan-500/15 border border-cyan-400/20 flex items-center justify-center text-cyan-300">
            <LockKeyhole size={22} />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70 font-semibold">Secure Access</p>
            <h1 className="text-2xl font-black text-white mt-1">Enter password to continue</h1>
          </div>
        </div>

        <p className="text-sm text-slate-300 leading-6">
          This screen protects the app from casual access. It is a frontend lock, so for production-grade security you should still protect the backend separately.
        </p>

        <div className="mt-6 space-y-3">
          <label className="block">
            <span className="text-[11px] uppercase tracking-[0.3em] text-slate-400 font-bold">Access password</span>
            <div className="mt-2 flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 focus-within:border-cyan-400/50 focus-within:ring-2 focus-within:ring-cyan-400/20 transition">
              <ShieldAlert size={18} className="text-slate-400 shrink-0" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                autoFocus
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (error) setError('');
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') submit();
                }}
                className="w-full bg-transparent outline-none text-white placeholder:text-slate-500"
                placeholder="Type password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(prev => !prev)}
                className="text-slate-400 hover:text-white transition"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>

          {error && (
            <p className="text-sm text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={submitting}
          className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-cyan-500 text-slate-950 font-black py-3.5 transition hover:bg-cyan-400 disabled:opacity-70 disabled:cursor-not-allowed"
        >
          <LockKeyhole size={18} />
          {submitting ? 'Checking...' : 'Unlock'}
        </button>
      </div>
    </div>
  );
}
