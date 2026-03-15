'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { ThemeToggle } from '@/lib/theme-context';

export default function LandingPage() {
    const { user } = useAuth();

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav className="px-6 py-6 md:px-10">
                <div className="mx-auto max-w-7xl flex items-center justify-between">
                    <Link href="/" className="flex items-center gap-2">
                        <div className="w-10 h-10 border-2 flex items-center justify-center" style={{ borderColor: 'var(--text-primary)' }}>
                            <span className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>A</span>
                        </div>
                        <span className="text-2xl font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>Avelon</span>
                    </Link>
                    <div className="flex items-center gap-2 md:gap-3">
                        <ThemeToggle />
                        <Link href="/leaderboard" className="btn-ghost text-sm">Leaderboard</Link>
                        <Link href="/failures" className="btn-ghost text-sm">Failure Explorer</Link>
                        <Link href="/datasets" className="btn-ghost text-sm">Dataset Manager</Link>
                        <Link href="/benchmark" className="btn-ghost text-sm">Benchmark Model</Link>
                        <Link href="/upload" className="btn-ghost text-sm">Compare Models</Link>
                        {user ? (
                            <Link href="/dashboard" className="btn-primary text-sm">Open Workspace</Link>
                        ) : (
                            <Link href="/register" className="btn-primary text-sm">Join Avelon</Link>
                        )}
                    </div>
                </div>
            </nav>

            <main className="mx-auto max-w-5xl px-6 pt-12 pb-24 text-center page-enter">
                <p className="text-sm uppercase tracking-[0.2em] mb-8" style={{ color: 'var(--text-tertiary)' }}>
                    AI Red-Team Infrastructure For Code Models
                </p>
                <h1 className="text-5xl md:text-7xl leading-[0.95] mb-8" style={{ color: 'var(--text-primary)' }}>
                    Stress-Test AI Reasoning
                    <br />
                    for smart contract security
                </h1>
                <p className="mx-auto max-w-3xl text-xl leading-relaxed mb-12" style={{ color: 'var(--text-secondary)' }}>
                    Avelon simulates attacker-style adversarial tasks, benchmarks model reliability, and exposes
                    reasoning failures with reproducible evidence.
                </p>

                <div className="flex flex-col sm:flex-row justify-center gap-3 mb-20">
                    <Link href={user ? '/upload' : '/register'} className="btn-primary text-base px-9 py-3">
                        Compare Models
                    </Link>
                    <Link href={user ? '/benchmark' : '/login'} className="btn-secondary text-base px-9 py-3">
                        Benchmark Model
                    </Link>
                </div>

                <div className="grid md:grid-cols-3 gap-4 text-left">
                    {[
                        {
                            title: 'Deterministic Evaluation',
                            body: 'Security scoring runs with fixed deterministic settings so results are reproducible and comparable.',
                        },
                        {
                            title: 'Failure-Centered Reports',
                            body: 'See missed critical findings, hallucinated vulnerabilities, and confidence-correctness mismatch patterns.',
                        },
                        {
                            title: 'Trust Decisions',
                            body: 'Outputs answer a concrete question: can this model be trusted for smart contract auditing?',
                        },
                    ].map((item) => (
                        <div key={item.title} className="card-hover p-6">
                            <h3 className="text-2xl mb-2" style={{ color: 'var(--text-primary)' }}>{item.title}</h3>
                            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{item.body}</p>
                        </div>
                    ))}
                </div>
            </main>
        </div>
    );
}
