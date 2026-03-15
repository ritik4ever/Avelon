'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { benchmarks, datasets, type DatasetRecord } from '@/lib/api';

const PROVIDERS = ['openai', 'anthropic', 'google', 'custom'] as const;

export default function BenchmarkPage() {
    const { user, token, loading: authLoading } = useAuth();
    const router = useRouter();
    const [provider, setProvider] = useState<(typeof PROVIDERS)[number]>('openai');
    const [modelName, setModelName] = useState('gpt-4o');
    const [apiKey, setApiKey] = useState('');
    const [apiBase, setApiBase] = useState('');
    const [datasetList, setDatasetList] = useState<DatasetRecord[]>([]);
    const [datasetId, setDatasetId] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [authLoading, user, router]);

    useEffect(() => {
        if (!token) return;
        const load = async () => {
            try {
                const items = await datasets.list(token);
                setDatasetList(items);
                const preferred = items.find((d) => d.status === 'ready');
                if (preferred) setDatasetId(preferred.id);
            } catch {
                // noop
            }
        };
        load();
    }, [token]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token) return;
        setSubmitting(true);
        setError('');
        try {
            const benchmark = await benchmarks.create(
                {
                    ai_provider: provider,
                    ai_model: modelName.trim(),
                    dataset_id: datasetId || undefined,
                    ai_temperature: 0.0,
                    custom_api_key: apiKey || undefined,
                    custom_api_base: apiBase || undefined,
                },
                token
            );
            router.push(`/benchmark/${benchmark.id}`);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to start benchmark');
            setSubmitting(false);
        }
    };

    if (authLoading || !user) return null;

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Benchmark Model</span>
                </div>
            </nav>

            <div className="max-w-2xl mx-auto px-6 py-10 page-enter">
                <h1 className="text-5xl leading-tight mb-2" style={{ color: 'var(--text-primary)' }}>
                    Benchmark Model Reliability
                </h1>
                <p className="text-sm mb-8" style={{ color: 'var(--text-tertiary)' }}>
                    Run one model across Avelon&apos;s curated safe and vulnerable contract dataset.
                </p>

                <form onSubmit={handleSubmit} className="card p-6 space-y-5">
                    {error && (
                        <div className="px-4 py-3 rounded-2xl text-sm" style={{ background: 'rgba(180,35,24,0.12)', color: 'var(--danger)' }}>
                            {error}
                        </div>
                    )}

                    <div>
                        <label className="label-text">Provider</label>
                        <div className="flex gap-2">
                            {PROVIDERS.map((p) => (
                                <button
                                    key={p}
                                    type="button"
                                    onClick={() => setProvider(p)}
                                    className="px-4 py-2 rounded-full text-sm transition-colors"
                                    style={{
                                        border: `1px solid ${provider === p ? 'var(--text-primary)' : 'var(--border-color)'}`,
                                        background: provider === p ? 'var(--bg-tertiary)' : 'transparent',
                                        color: 'var(--text-primary)',
                                    }}
                                >
                                    {p}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="label-text">Model Name</label>
                        <input
                            className="input-field"
                            value={modelName}
                            onChange={(e) => setModelName(e.target.value)}
                            placeholder="gpt-4o / claude-3-5-sonnet / gemini-1.5-pro"
                            required
                        />
                    </div>

                    <div>
                        <label className="label-text">Dataset Version</label>
                        <select
                            className="input-field"
                            value={datasetId}
                            onChange={(e) => setDatasetId(e.target.value)}
                        >
                            <option value="">Default local dataset</option>
                            {datasetList.map((dataset) => (
                                <option key={dataset.id} value={dataset.id}>
                                    {dataset.dataset_version} ({dataset.task_count} tasks, {dataset.status})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="label-text">API Key</label>
                        <input
                            className="input-field"
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder="Optional if server-side key is configured"
                        />
                    </div>

                    <div>
                        <label className="label-text">API Base URL (optional)</label>
                        <input
                            className="input-field"
                            value={apiBase}
                            onChange={(e) => setApiBase(e.target.value)}
                            placeholder="https://api.provider.com/v1"
                        />
                    </div>

                    <div className="rounded-2xl p-4 text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                        Output includes aggregate precision, recall, hallucination rate, weighted reliability,
                        and per-vulnerability-category performance.
                    </div>

                    <button type="submit" disabled={submitting} className="btn-primary w-full py-3 text-base">
                        {submitting ? 'Running benchmark...' : 'Start Benchmark'}
                    </button>
                </form>
            </div>
        </div>
    );
}
