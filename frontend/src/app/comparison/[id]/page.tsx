'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { comparisons, type ComparisonResult, type ComparisonRun } from '@/lib/api';
import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

export default function ComparisonPage() {
    const params = useParams();
    const router = useRouter();
    const { user, token, loading: authLoading } = useAuth();
    const [comparison, setComparison] = useState<ComparisonRun | null>(null);
    const [results, setResults] = useState<ComparisonResult[]>([]);
    const [loading, setLoading] = useState(true);

    const comparisonId = params.id as string;

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [authLoading, user, router]);

    useEffect(() => {
        if (!token || !comparisonId) return;
        const poll = async () => {
            try {
                const [run, rows] = await Promise.all([
                    comparisons.get(comparisonId, token),
                    comparisons.results(comparisonId, token),
                ]);
                setComparison(run);
                setResults(rows);
            } catch {
                // noop
            }
            setLoading(false);
        };
        poll();
        const interval = setInterval(poll, 4000);
        return () => clearInterval(interval);
    }, [token, comparisonId]);

    const chartRows = useMemo(
        () =>
            results.map((row) => ({
                model: row.ai_model,
                precision: (row.precision_score || 0) * 100,
                recall: (row.recall_score || 0) * 100,
                reliability: (row.reliability_score || 0) * 100,
                hallucination: (row.hallucination_rate || 0) * 100,
            })),
        [results]
    );

    if (authLoading || !user || loading || !comparison) return null;

    const isRunning = comparison.status === 'queued' || comparison.status === 'running';
    const progress = comparison.total_models > 0
        ? ((comparison.completed_models / comparison.total_models) * 100).toFixed(0)
        : '0';

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Model Comparison</span>
                </div>
            </nav>

            <div className="max-w-6xl mx-auto px-6 py-8 page-enter">
                <div className="flex flex-col md:flex-row justify-between md:items-end gap-4 mb-6">
                    <div>
                        <h1 className="text-5xl leading-none mb-2" style={{ color: 'var(--text-primary)' }}>
                            Reliability Comparison
                        </h1>
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            Compare precision, recall, hallucination rate, miss rate, and weighted reliability.
                        </p>
                    </div>
                    <div className="card p-4 min-w-[210px]">
                        <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Average Reliability</p>
                        <p className="text-3xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                            {comparison.avg_reliability_score != null
                                ? `${(comparison.avg_reliability_score * 100).toFixed(1)}%`
                                : '—'}
                        </p>
                    </div>
                </div>

                {isRunning && (
                    <div className="card p-4 mb-6">
                        <div className="flex items-center justify-between text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                            <span>Comparison in progress</span>
                            <span>{progress}%</span>
                        </div>
                        <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-tertiary)' }}>
                            <div className="h-full rounded-full" style={{ width: `${progress}%`, background: 'var(--accent)' }} />
                        </div>
                    </div>
                )}

                <div className="grid md:grid-cols-2 gap-4 mb-6">
                    <div className="card p-5">
                        <h3 className="text-2xl mb-4" style={{ color: 'var(--text-primary)' }}>Reliability by Model</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={chartRows}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                                <XAxis dataKey="model" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                <Tooltip />
                                <Bar dataKey="reliability" fill="#af2f22" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="card p-5">
                        <h3 className="text-2xl mb-4" style={{ color: 'var(--text-primary)' }}>Precision vs Recall</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={chartRows}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                                <XAxis dataKey="model" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                <Tooltip />
                                <Bar dataKey="precision" fill="#171716" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="recall" fill="#7c7467" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="card overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                {['Model', 'Precision', 'Recall', 'Hallucination', 'Miss Rate', 'Reliability'].map((head) => (
                                    <th key={head} className="px-4 py-3 text-left text-xs" style={{ color: 'var(--text-tertiary)' }}>
                                        {head}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {results.map((row) => (
                                <tr key={row.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                    <td className="px-4 py-3">
                                        <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{row.ai_model}</div>
                                        <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{row.ai_provider}</div>
                                    </td>
                                    <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        {row.precision_score != null ? `${(row.precision_score * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        {row.recall_score != null ? `${(row.recall_score * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        {row.hallucination_rate != null ? `${(row.hallucination_rate * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        {row.miss_rate != null ? `${(row.miss_rate * 100).toFixed(1)}%` : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-sm font-semibold" style={{ color: 'var(--accent)' }}>
                                        {row.reliability_score != null ? `${(row.reliability_score * 100).toFixed(1)}%` : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
