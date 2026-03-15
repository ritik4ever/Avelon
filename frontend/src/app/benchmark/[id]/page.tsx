'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { benchmarks, type BenchmarkRun } from '@/lib/api';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function BenchmarkRunPage() {
    const params = useParams();
    const router = useRouter();
    const { user, token, loading: authLoading } = useAuth();
    const [benchmark, setBenchmark] = useState<BenchmarkRun | null>(null);
    const [loading, setLoading] = useState(true);

    const benchmarkId = params.id as string;

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [authLoading, user, router]);

    useEffect(() => {
        if (!token || !benchmarkId) return;
        const poll = async () => {
            try {
                setBenchmark(await benchmarks.get(benchmarkId, token));
            } catch {
                // noop
            }
            setLoading(false);
        };
        poll();
        const interval = setInterval(poll, 5000);
        return () => clearInterval(interval);
    }, [token, benchmarkId]);

    const categoryRows = useMemo(() => {
        if (!benchmark?.category_performance) return [];
        return Object.entries(benchmark.category_performance).map(([category, stats]) => ({
            category: category.replace(/_/g, ' '),
            reliability: stats.reliability * 100,
            precision: stats.precision * 100,
            recall: stats.recall * 100,
        }));
    }, [benchmark]);

    const difficultyRows = useMemo(() => {
        if (!benchmark?.difficulty_performance) return [];
        return Object.entries(benchmark.difficulty_performance).map(([difficulty, stats]) => ({
            difficulty,
            reliability: stats.reliability * 100,
            precision: stats.precision * 100,
            recall: stats.recall * 100,
            count: stats.count,
        }));
    }, [benchmark]);

    if (authLoading || !user || loading || !benchmark) return null;

    const isRunning = benchmark.status === 'queued' || benchmark.status === 'running';
    const progress = benchmark.total_contracts > 0
        ? ((benchmark.completed_contracts / benchmark.total_contracts) * 100).toFixed(0)
        : '0';

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Benchmark Result</span>
                </div>
            </nav>

            <div className="max-w-6xl mx-auto px-6 py-8 page-enter">
                <div className="flex flex-col md:flex-row justify-between md:items-end gap-4 mb-6">
                    <div>
                        <h1 className="text-5xl leading-none mb-2" style={{ color: 'var(--text-primary)' }}>
                            {benchmark.ai_model}
                        </h1>
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            Provider: {benchmark.ai_provider} | Status: {benchmark.status}
                        </p>
                    </div>
                    <div className="card p-4 min-w-[240px]">
                        <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Weighted Reliability</p>
                        <p className="text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                            {benchmark.avg_reliability_score != null
                                ? `${(benchmark.avg_reliability_score * 100).toFixed(1)}%`
                                : '—'}
                        </p>
                        {benchmark.benchmark_summary && (
                            <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                                {benchmark.benchmark_summary}
                            </p>
                        )}
                    </div>
                </div>

                {isRunning && (
                    <div className="card p-4 mb-6">
                        <div className="flex items-center justify-between text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                            <span>Benchmark in progress</span>
                            <span>{progress}%</span>
                        </div>
                        <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-tertiary)' }}>
                            <div className="h-full rounded-full" style={{ width: `${progress}%`, background: 'var(--accent)' }} />
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
                    {[
                        { label: 'Precision', value: benchmark.avg_precision },
                        { label: 'Recall', value: benchmark.avg_recall },
                        { label: 'Hallucination', value: benchmark.avg_hallucination_rate },
                        { label: 'Miss Rate', value: benchmark.avg_miss_rate },
                        { label: 'Latency', raw: benchmark.avg_latency_ms != null ? `${benchmark.avg_latency_ms.toFixed(0)} ms` : '—' },
                        { label: 'Total Cost', raw: benchmark.total_estimated_cost_usd != null ? `$${benchmark.total_estimated_cost_usd.toFixed(4)}` : '—' },
                    ].map((metric) => (
                        <div key={metric.label} className="card p-4 text-center">
                            <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{metric.label}</p>
                            <p className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                                {'raw' in metric
                                    ? metric.raw
                                    : metric.value != null
                                        ? `${(metric.value * 100).toFixed(1)}%`
                                        : '—'}
                            </p>
                        </div>
                    ))}
                </div>

                {categoryRows.length > 0 && (
                    <div className="grid md:grid-cols-2 gap-4 mb-4">
                        <div className="card p-5">
                            <h3 className="text-2xl mb-4" style={{ color: 'var(--text-primary)' }}>Category Reliability</h3>
                            <ResponsiveContainer width="100%" height={320}>
                                <BarChart data={categoryRows}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                                    <XAxis dataKey="category" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                    <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                    <Tooltip />
                                    <Bar dataKey="reliability" fill="#af2f22" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>

                        <div className="card p-5 overflow-x-auto">
                            <h3 className="text-2xl mb-4" style={{ color: 'var(--text-primary)' }}>Per-Category Metrics</h3>
                            <table className="w-full text-sm">
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                        {['Category', 'Precision', 'Recall', 'Reliability'].map((head) => (
                                            <th key={head} className="text-left py-2" style={{ color: 'var(--text-tertiary)' }}>{head}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {categoryRows.map((row) => (
                                        <tr key={row.category} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                            <td className="py-2" style={{ color: 'var(--text-primary)' }}>{row.category}</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.precision.toFixed(1)}%</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.recall.toFixed(1)}%</td>
                                            <td className="py-2 font-semibold" style={{ color: 'var(--accent)' }}>{row.reliability.toFixed(1)}%</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {difficultyRows.length > 0 && (
                    <div className="card p-5 overflow-x-auto">
                        <h3 className="text-2xl mb-4" style={{ color: 'var(--text-primary)' }}>Detection by Difficulty</h3>
                        <table className="w-full text-sm">
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                    {['Difficulty', 'Tasks', 'Precision', 'Recall', 'Reliability'].map((head) => (
                                        <th key={head} className="text-left py-2" style={{ color: 'var(--text-tertiary)' }}>{head}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {difficultyRows.map((row) => (
                                    <tr key={row.difficulty} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                        <td className="py-2" style={{ color: 'var(--text-primary)' }}>{row.difficulty}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.count}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.precision.toFixed(1)}%</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.recall.toFixed(1)}%</td>
                                        <td className="py-2" style={{ color: 'var(--accent)' }}>{row.reliability.toFixed(1)}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
