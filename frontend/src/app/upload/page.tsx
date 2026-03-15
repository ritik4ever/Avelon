'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { comparisons, contracts } from '@/lib/api';

type ModelOption = {
    provider: 'openai' | 'anthropic' | 'google' | 'custom';
    model: string;
    label: string;
    vendor: string;
};

const MODEL_OPTIONS: ModelOption[] = [
    { provider: 'openai', model: 'gpt-4o', label: 'GPT-4o', vendor: 'OpenAI' },
    { provider: 'openai', model: 'gpt-4o-mini', label: 'GPT-4o Mini', vendor: 'OpenAI' },
    { provider: 'openai', model: 'gpt-4-turbo', label: 'GPT-4 Turbo', vendor: 'OpenAI' },
    { provider: 'anthropic', model: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet', vendor: 'Anthropic' },
    { provider: 'anthropic', model: 'claude-3-opus-20240229', label: 'Claude 3 Opus', vendor: 'Anthropic' },
    { provider: 'google', model: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro', vendor: 'Google' },
];

export default function UploadPage() {
    const { user, token, loading: authLoading } = useAuth();
    const router = useRouter();
    const [file, setFile] = useState<File | null>(null);
    const [dragOver, setDragOver] = useState(false);
    const [selected, setSelected] = useState<number[]>([0, 3]);
    const [customApiKey, setCustomApiKey] = useState('');
    const [customApiBase, setCustomApiBase] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [authLoading, user, router]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const incoming = e.dataTransfer.files[0];
        if (incoming?.name.endsWith('.sol')) {
            setFile(incoming);
            setError('');
        } else {
            setError('Only Solidity (.sol) files are accepted');
        }
    }, []);

    const toggleModel = (index: number) => {
        setSelected((prev) => (
            prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
        ));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file || !token) return;
        if (selected.length < 2) {
            setError('Select at least two models for reliability comparison');
            return;
        }

        setError('');
        setSubmitting(true);
        try {
            const contract = await contracts.upload(file, token);
            const models = selected.map((index) => {
                const option = MODEL_OPTIONS[index];
                const requiresDirectApi = option.provider === 'custom' || option.provider === 'google';
                return {
                    ai_provider: option.provider,
                    ai_model: option.model,
                    custom_api_key: requiresDirectApi ? customApiKey || undefined : undefined,
                    custom_api_base: option.provider === 'custom' ? customApiBase || undefined : undefined,
                };
            });

            const run = await comparisons.create({
                contract_id: contract.id,
                models,
                ai_temperature: 0.0,
            }, token);
            router.push(`/comparison/${run.id}`);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to start comparison');
            setSubmitting(false);
        }
    };

    if (authLoading || !user) return null;

    const customSelected = selected.some((index) => ['custom', 'google'].includes(MODEL_OPTIONS[index].provider));

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">Back</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Model Comparison
                    </span>
                </div>
            </nav>

            <div className="max-w-3xl mx-auto px-6 py-10 page-enter">
                <h1 className="text-5xl leading-tight mb-2" style={{ color: 'var(--text-primary)' }}>
                    Evaluate AI Reliability for Smart Contract Security
                </h1>
                <p className="text-sm mb-8" style={{ color: 'var(--text-tertiary)' }}>
                    Upload one contract, run multiple models, and compare reliability metrics side by side.
                </p>

                <form onSubmit={handleSubmit} className="space-y-6">
                    {error && (
                        <div className="px-4 py-3 rounded-2xl text-sm" style={{ background: 'rgba(180,35,24,0.12)', color: 'var(--danger)' }}>
                            {error}
                        </div>
                    )}

                    <div
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={handleDrop}
                        className="relative rounded-2xl p-10 text-center transition-all duration-200 cursor-pointer"
                        style={{
                            border: `2px dashed ${dragOver || file ? 'var(--accent)' : 'var(--border-color)'}`,
                            background: file ? 'rgba(18,183,106,0.09)' : 'var(--bg-secondary)',
                        }}
                    >
                        <input
                            type="file"
                            accept=".sol"
                            onChange={(e) => {
                                const incoming = e.target.files?.[0];
                                if (incoming?.name.endsWith('.sol')) {
                                    setFile(incoming);
                                    setError('');
                                } else {
                                    setError('Only Solidity (.sol) files are accepted');
                                }
                            }}
                            className="absolute inset-0 opacity-0 cursor-pointer"
                        />
                        {file ? (
                            <>
                                <p className="text-xl font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{file.name}</p>
                                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>{(file.size / 1024).toFixed(1)} KB</p>
                            </>
                        ) : (
                            <>
                                <p className="text-xl font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Drop Solidity file here</p>
                                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>or click to browse</p>
                            </>
                        )}
                    </div>

                    <div>
                        <label className="label-text">Select Models (2+)</label>
                        <div className="grid md:grid-cols-3 gap-3">
                            {MODEL_OPTIONS.map((model, index) => {
                                const active = selected.includes(index);
                                return (
                                    <button
                                        key={`${model.provider}-${model.model}`}
                                        type="button"
                                        onClick={() => toggleModel(index)}
                                        className="p-4 rounded-2xl text-left transition-all duration-200"
                                        style={{
                                            border: `1px solid ${active ? 'var(--text-primary)' : 'var(--border-color)'}`,
                                            background: active ? 'var(--bg-tertiary)' : 'var(--bg-elevated)',
                                        }}
                                    >
                                        <div className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{model.label}</div>
                                        <div className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{model.vendor}</div>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {customSelected && (
                        <div className="card p-5 space-y-4">
                            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                                Provider API access
                            </p>
                            <div>
                                <label className="label-text">API Key</label>
                                <input
                                    className="input-field"
                                    type="password"
                                    value={customApiKey}
                                    onChange={(e) => setCustomApiKey(e.target.value)}
                                    placeholder="Optional for custom providers"
                                />
                            </div>
                            <div>
                                <label className="label-text">API Base URL</label>
                                <input
                                    className="input-field"
                                    value={customApiBase}
                                    onChange={(e) => setCustomApiBase(e.target.value)}
                                    placeholder="https://api.your-provider.com/v1"
                                />
                            </div>
                        </div>
                    )}

                    <div className="rounded-2xl p-4 text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                        Deterministic scoring is enforced for reliability reproducibility.
                    </div>

                    <button type="submit" disabled={!file || submitting} className="btn-primary w-full py-3 text-base">
                        {submitting ? 'Starting comparison...' : 'Run Reliability Comparison'}
                    </button>
                </form>
            </div>
        </div>
    );
}
