'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { ThemeToggle } from '@/lib/theme-context';

export default function LoginPage() {
    const { login } = useAuth();
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(email, password);
            router.push('/dashboard');
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-6" style={{ background: 'var(--bg-primary)' }}>
            <div className="absolute top-4 right-4"><ThemeToggle /></div>
            <div className="w-full max-w-sm">
                <div className="text-center mb-8">
                    <Link href="/" className="inline-flex items-center gap-2 mb-6">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--text-primary)' }}>
                            <span className="text-xs font-bold" style={{ color: 'var(--bg-primary)' }}>AVL</span>
                        </div>
                    </Link>
                    <h1 className="text-xl font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Welcome back</h1>
                    <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Sign in to your Avelon workspace</p>
                </div>

                <form onSubmit={handleSubmit} className="card p-6 space-y-4">
                    {error && (
                        <div className="px-3 py-2 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.08)', color: 'var(--danger)' }}>
                            {error}
                        </div>
                    )}
                    <div>
                        <label htmlFor="email" className="label-text">Email</label>
                        <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="input-field" placeholder="you@example.com" />
                    </div>
                    <div>
                        <label htmlFor="password" className="label-text">Password</label>
                        <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" placeholder="••••••••" />
                    </div>
                    <button type="submit" disabled={loading} className="btn-primary w-full">
                        {loading ? 'Signing in…' : 'Sign In'}
                    </button>
                </form>

                <p className="text-center text-xs mt-5" style={{ color: 'var(--text-tertiary)' }}>
                    Don&apos;t have an account?{' '}
                    <Link href="/register" className="font-medium hover:opacity-70 transition-opacity" style={{ color: 'var(--text-primary)' }}>Create one</Link>
                </p>
            </div>
        </div>
    );
}
