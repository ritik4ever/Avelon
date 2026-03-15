'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Pie, PieChart, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { failures, type FailureRecord, type FailureSummary } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

const COLORS = ['#af2f22', '#175cd3', '#b54708', '#067647', '#7a5af8', '#475467'];

export default function FailuresPage() {
    const { token, user, loading: authLoading } = useAuth();
    const router = useRouter();
    const [rows, setRows] = useState<FailureRecord[]>([]);
    const [summary, setSummary] = useState<FailureSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [authLoading, user, router]);

    useEffect(() => {
        if (!token) return;
        const load = async () => {
            try {
                const [allFailures, stats] = await Promise.all([
                    failures.list(token, { limit: 500 }),
                    failures.summary(token),
                ]);
                setRows(allFailures);
                setSummary(stats);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load failures');
            }
            setLoading(false);
        };
        load();
    }, [token]);

    if (authLoading || !user) return null;

    const pieData = useMemo(() => {
        if (!summary) return [];
        return Object.entries(summary.by_type).map(([name, value]) => ({ name, value }));
    }, [summary]);

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Failure Explorer</span>
                </div>
            </nav>

            <main className="max-w-6xl mx-auto px-6 py-8 page-enter">
                <h1 className="text-5xl mb-2" style={{ color: 'var(--text-primary)' }}>
                    AI Reasoning Failure Explorer
                </h1>
                <p className="text-sm mb-8" style={{ color: 'var(--text-tertiary)' }}>
                    Investigate hallucinations, misses, overconfidence, and vulnerability-type confusions.
                </p>

                {error && <p className="text-sm mb-4" style={{ color: 'var(--danger)' }}>{error}</p>}

                <div className="grid md:grid-cols-2 gap-4 mb-6">
                    <div className="card p-5">
                        <h2 className="text-3xl mb-3" style={{ color: 'var(--text-primary)' }}>Failure Type Distribution</h2>
                        <div className="h-72">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={100} label>
                                        {pieData.map((entry, idx) => (
                                            <Cell key={entry.name} fill={COLORS[idx % COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                    <div className="card p-5">
                        <h2 className="text-3xl mb-3" style={{ color: 'var(--text-primary)' }}>Summary</h2>
                        {summary ? (
                            <div className="space-y-2 text-sm">
                                <p style={{ color: 'var(--text-primary)' }}>Total Failures: {summary.total_failures}</p>
                                {Object.entries(summary.by_severity).map(([severity, count]) => (
                                    <p key={severity} style={{ color: 'var(--text-secondary)' }}>
                                        {severity}: {count}
                                    </p>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No failure data yet.</p>
                        )}
                    </div>
                </div>

                <div className="card p-5">
                    <h2 className="text-3xl mb-3" style={{ color: 'var(--text-primary)' }}>Recent Failures</h2>
                    {loading ? (
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading...</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                        {['Type', 'Severity', 'Vulnerability', 'Confidence', 'Evaluation', 'Created'].map((label) => (
                                            <th key={label} className="text-left py-2" style={{ color: 'var(--text-tertiary)' }}>{label}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row) => (
                                        <tr key={row.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                            <td className="py-2" style={{ color: 'var(--text-primary)' }}>{row.failure_type}</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.severity}</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.vulnerability_type || '-'}</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>
                                                {row.confidence != null ? `${(row.confidence * 100).toFixed(0)}%` : '-'}
                                            </td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.evaluation_id.slice(0, 8)}</td>
                                            <td className="py-2" style={{ color: 'var(--text-secondary)' }}>
                                                {new Date(row.created_at).toLocaleString()}
                                            </td>
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
