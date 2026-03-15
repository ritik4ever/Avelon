'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { datasets, type DatasetRecord } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export default function DatasetManagerPage() {
    const { token, user, loading: authLoading } = useAuth();
    const router = useRouter();
    const [rows, setRows] = useState<DatasetRecord[]>([]);
    const [name, setName] = useState('Avelon Adversarial Solidity');
    const [version, setVersion] = useState('');
    const [taskCount, setTaskCount] = useState(40);
    const [method, setMethod] = useState('mixed');
    const [categories, setCategories] = useState('reentrancy_edge_case,hidden_access_control,proxy_upgradeable_trap');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const refresh = async () => {
        if (!token) return;
        setRows(await datasets.list(token));
    };

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [authLoading, user, router]);

    useEffect(() => {
        if (!token) return;
        refresh().catch(() => undefined);
    }, [token]);

    if (authLoading || !user) return null;

    const createDataset = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token) return;
        setLoading(true);
        setError('');
        try {
            await datasets.generate(
                {
                    name,
                    dataset_version: version || undefined,
                    generation_method: method,
                    task_count: taskCount,
                    categories: categories.split(',').map((c) => c.trim()).filter(Boolean),
                    difficulty_mix: { easy: 0.2, medium: 0.35, hard: 0.3, adversarial: 0.15 },
                },
                token
            );
            await refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create dataset');
        }
        setLoading(false);
    };

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Dataset Manager</span>
                </div>
            </nav>

            <main className="max-w-6xl mx-auto px-6 py-8 page-enter">
                <h1 className="text-5xl mb-2" style={{ color: 'var(--text-primary)' }}>
                    Adversarial Dataset Manager
                </h1>
                <p className="text-sm mb-8" style={{ color: 'var(--text-tertiary)' }}>
                    Create immutable dataset versions for reproducible AI red-team benchmarking.
                </p>

                <form onSubmit={createDataset} className="card p-5 mb-6 grid md:grid-cols-2 gap-4">
                    {error && <p className="text-sm md:col-span-2" style={{ color: 'var(--danger)' }}>{error}</p>}
                    <div>
                        <label className="label-text">Dataset Name</label>
                        <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} required />
                    </div>
                    <div>
                        <label className="label-text">Dataset Version (optional)</label>
                        <input className="input-field" value={version} onChange={(e) => setVersion(e.target.value)} />
                    </div>
                    <div>
                        <label className="label-text">Generation Method</label>
                        <select className="input-field" value={method} onChange={(e) => setMethod(e.target.value)}>
                            <option value="mixed">mixed</option>
                            <option value="template">template</option>
                            <option value="mutation">mutation</option>
                            <option value="fuzzing">fuzzing</option>
                        </select>
                    </div>
                    <div>
                        <label className="label-text">Task Count</label>
                        <input
                            className="input-field"
                            type="number"
                            min={1}
                            max={5000}
                            value={taskCount}
                            onChange={(e) => setTaskCount(Number(e.target.value))}
                        />
                    </div>
                    <div className="md:col-span-2">
                        <label className="label-text">Categories (comma separated)</label>
                        <input className="input-field" value={categories} onChange={(e) => setCategories(e.target.value)} />
                    </div>
                    <button className="btn-primary md:col-span-2 py-3" disabled={loading}>
                        {loading ? 'Generating dataset...' : 'Generate Dataset'}
                    </button>
                </form>

                <div className="card p-5">
                    <h2 className="text-3xl mb-4" style={{ color: 'var(--text-primary)' }}>Dataset Versions</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                    {['Version', 'Name', 'Method', 'Tasks', 'Status', 'Created'].map((label) => (
                                        <th key={label} className="text-left py-2" style={{ color: 'var(--text-tertiary)' }}>{label}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((row) => (
                                    <tr key={row.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                        <td className="py-2" style={{ color: 'var(--text-primary)' }}>{row.dataset_version}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.name}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.generation_method}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.task_count}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{row.status}</td>
                                        <td className="py-2" style={{ color: 'var(--text-secondary)' }}>
                                            {new Date(row.created_at).toLocaleString()}
                                        </td>
                                    </tr>
                                ))}
                                {rows.length === 0 && (
                                    <tr>
                                        <td className="py-4 text-sm" colSpan={6} style={{ color: 'var(--text-tertiary)' }}>
                                            No datasets yet.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
        </div>
    );
}
