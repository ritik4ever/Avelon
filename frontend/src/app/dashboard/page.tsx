'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { ThemeToggle } from '@/lib/theme-context';
import {
    benchmarks,
    comparisons,
    evaluations,
    type BenchmarkRun,
    type ComparisonRun,
    type Evaluation,
} from '@/lib/api';

export default function DashboardPage() {
    const { user, token, loading: authLoading, logout } = useAuth();
    const router = useRouter();
    const [comparisonRuns, setComparisonRuns] = useState<ComparisonRun[]>([]);
    const [benchmarkRuns, setBenchmarkRuns] = useState<BenchmarkRun[]>([]);
    const [recentEvaluations, setRecentEvaluations] = useState<Evaluation[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [user, authLoading, router]);

    useEffect(() => {
        if (!token) return;
        const load = async () => {
            try {
                const [comp, bench, evals] = await Promise.all([
                    comparisons.list(token),
                    benchmarks.list(token),
                    evaluations.list(token),
                ]);
                setComparisonRuns(comp);
                setBenchmarkRuns(bench);
                setRecentEvaluations(evals.slice(0, 6));
            } catch {
                // noop
            }
            setLoading(false);
        };
        load();
        const interval = setInterval(load, 10000);
        return () => clearInterval(interval);
    }, [token]);

    if (authLoading || !user) return null;

    const comparisonReliability = comparisonRuns
        .filter((c) => c.avg_reliability_score != null)
        .map((c) => c.avg_reliability_score || 0);
    const avgComparisonReliability = comparisonReliability.length
        ? `${((comparisonReliability.reduce((a, b) => a + b, 0) / comparisonReliability.length) * 100).toFixed(1)}%`
        : '—';

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav className="sticky top-0 z-50" style={{ background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
                    <Link href="/" className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Avelon</Link>
                    <div className="flex items-center gap-2">
                        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{user.email}</span>
                        <ThemeToggle />
                        <button onClick={logout} className="btn-ghost text-xs">Sign Out</button>
                    </div>
                </div>
            </nav>

            <div className="max-w-6xl mx-auto px-6 py-8 page-enter">
                <div className="flex flex-col md:flex-row justify-between md:items-end gap-4 mb-8">
                    <div>
                        <h1 className="text-5xl leading-none mb-2" style={{ color: 'var(--text-primary)' }}>
                            Reliability Workspace
                        </h1>
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            Compare models, benchmark reliability, and track trust signals over time.
                        </p>
                    </div>
                    <div className="flex gap-2">
                        <Link href="/upload" className="btn-primary text-sm">Compare Models</Link>
                        <Link href="/benchmark" className="btn-secondary text-sm">Benchmark Model</Link>
                        <Link href="/datasets" className="btn-secondary text-sm">Datasets</Link>
                        <Link href="/failures" className="btn-secondary text-sm">Failures</Link>
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                    {[
                        { label: 'Comparisons', value: comparisonRuns.length },
                        { label: 'Benchmarks', value: benchmarkRuns.length },
                        { label: 'Completed Evaluations', value: recentEvaluations.filter((e) => e.status === 'report_ready').length },
                        { label: 'Avg Comparison Reliability', value: avgComparisonReliability },
                    ].map((card) => (
                        <div key={card.label} className="card p-4">
                            <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{card.label}</p>
                            <p className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>{card.value}</p>
                        </div>
                    ))}
                </div>

                <div className="grid md:grid-cols-2 gap-4 mb-8">
                    <div className="card p-5">
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="text-3xl" style={{ color: 'var(--text-primary)' }}>Recent Comparisons</h2>
                            <Link href="/upload" className="text-sm" style={{ color: 'var(--accent)' }}>New</Link>
                        </div>
                        {loading ? (
                            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading...</p>
                        ) : comparisonRuns.length === 0 ? (
                            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No comparison runs yet.</p>
                        ) : (
                            <div className="space-y-2">
                                {comparisonRuns.slice(0, 6).map((run) => (
                                    <Link
                                        key={run.id}
                                        href={`/comparison/${run.id}`}
                                        className="block rounded-2xl px-3 py-3 transition-colors"
                                        style={{ background: 'var(--bg-secondary)' }}
                                    >
                                        <div className="flex items-center justify-between">
                                            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                                                {run.completed_models}/{run.total_models} models
                                            </p>
                                            <p className="text-sm" style={{ color: 'var(--accent)' }}>
                                                {run.avg_reliability_score != null ? `${(run.avg_reliability_score * 100).toFixed(1)}%` : '—'}
                                            </p>
                                        </div>
                                        <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{run.status}</p>
                                    </Link>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="card p-5">
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="text-3xl" style={{ color: 'var(--text-primary)' }}>Benchmark History</h2>
                            <Link href="/benchmark" className="text-sm" style={{ color: 'var(--accent)' }}>Run</Link>
                        </div>
                        {loading ? (
                            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading...</p>
                        ) : benchmarkRuns.length === 0 ? (
                            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No benchmark runs yet.</p>
                        ) : (
                            <div className="space-y-2">
                                {benchmarkRuns.slice(0, 6).map((run) => (
                                    <Link
                                        key={run.id}
                                        href={`/benchmark/${run.id}`}
                                        className="block rounded-2xl px-3 py-3 transition-colors"
                                        style={{ background: 'var(--bg-secondary)' }}
                                    >
                                        <div className="flex items-center justify-between">
                                            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                                                {run.ai_model}
                                            </p>
                                            <p className="text-sm" style={{ color: 'var(--accent)' }}>
                                                {run.avg_reliability_score != null ? `${(run.avg_reliability_score * 100).toFixed(1)}%` : '—'}
                                            </p>
                                        </div>
                                        <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                                            {run.ai_provider} • {run.status}
                                        </p>
                                    </Link>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div className="card p-5">
                    <h2 className="text-3xl mb-3" style={{ color: 'var(--text-primary)' }}>Recent Reliability Reports</h2>
                    {recentEvaluations.length === 0 ? (
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No evaluations yet.</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                        {['Model', 'Status', 'Precision', 'Recall', 'Reliability', 'Report'].map((head) => (
                                            <th key={head} className="text-left text-xs py-2" style={{ color: 'var(--text-tertiary)' }}>{head}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {recentEvaluations.map((ev) => (
                                        <tr key={ev.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                            <td className="py-2 text-sm" style={{ color: 'var(--text-primary)' }}>{ev.ai_model}</td>
                                            <td className="py-2 text-sm" style={{ color: 'var(--text-secondary)' }}>{ev.status}</td>
                                            <td className="py-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                                {ev.precision_score != null ? `${(ev.precision_score * 100).toFixed(1)}%` : '—'}
                                            </td>
                                            <td className="py-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                                {ev.recall_score != null ? `${(ev.recall_score * 100).toFixed(1)}%` : '—'}
                                            </td>
                                            <td className="py-2 text-sm" style={{ color: 'var(--accent)' }}>
                                                {ev.reliability_score != null ? `${(ev.reliability_score * 100).toFixed(1)}%` : '—'}
                                            </td>
                                            <td className="py-2 text-sm">
                                                <Link
                                                    href={ev.status === 'report_ready' ? `/results/${ev.id}` : `/processing/${ev.id}`}
                                                    style={{ color: 'var(--text-primary)' }}
                                                >
                                                    Open
                                                </Link>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
