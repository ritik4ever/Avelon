'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { leaderboard, type LeaderboardModel } from '@/lib/api';

export default function LeaderboardPage() {
    const [rows, setRows] = useState<LeaderboardModel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const load = async () => {
            try {
                setRows(await leaderboard.models(25));
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load leaderboard');
            }
            setLoading(false);
        };
        load();
    }, []);

    const chartData = useMemo(
        () =>
            rows.slice(0, 8).map((row) => ({
                model: `${row.provider}:${row.model_name}`.slice(0, 24),
                reliability: Number((row.reliability_score * 100).toFixed(1)),
            })),
        [rows]
    );

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Model Leaderboard</span>
                </div>
            </nav>

            <main className="max-w-6xl mx-auto px-6 py-8 page-enter">
                <h1 className="text-5xl mb-2" style={{ color: 'var(--text-primary)' }}>
                    Public Reliability Leaderboard
                </h1>
                <p className="text-sm mb-8" style={{ color: 'var(--text-tertiary)' }}>
                    Ranked by weighted reliability score across completed adversarial benchmarks.
                </p>

                {error && <p className="text-sm mb-4" style={{ color: 'var(--danger)' }}>{error}</p>}

                <div className="card p-5 mb-6">
                    <h2 className="text-3xl mb-4" style={{ color: 'var(--text-primary)' }}>Top Reliability Scores</h2>
                    <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                                <XAxis dataKey="model" stroke="var(--text-tertiary)" />
                                <YAxis stroke="var(--text-tertiary)" />
                                <Tooltip />
                                <Bar dataKey="reliability" fill="var(--accent)" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="card p-5">
                    <h2 className="text-3xl mb-4" style={{ color: 'var(--text-primary)' }}>Ranking</h2>
                    {loading ? (
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading...</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                        {['Rank', 'Model', 'Reliability', 'Hallucination', 'Miss', 'Latency', 'Runs'].map((label) => (
                                            <th key={label} className="text-left py-2" style={{ color: 'var(--text-tertiary)' }}>{label}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row) => (
                                        <tr key={`${row.provider}-${row.model_name}-${row.rank}`} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                            <td className="py-2" style={{ color: 'var(--text-primary)' }}>{row.rank}</td>
                                            <td className="py-2" style={{ color: 'var(--text-primary)' }}>{row.provider}:{row.model_name}</td>
                                            <td className="py-2" style={{ color: 'var(--accent)' }}>{(row.reliability_score * 100).toFixed(1)}%</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{(row.hallucination_rate * 100).toFixed(1)}%</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{(row.miss_rate * 100).toFixed(1)}%</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.average_latency_ms.toFixed(0)} ms</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.benchmark_runs}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
