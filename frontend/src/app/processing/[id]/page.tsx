'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { evaluations, type Evaluation } from '@/lib/api';

const PIPELINE_STEPS = [
    { key: 'queued', label: 'Queued' },
    { key: 'preprocessing', label: 'Preprocessing' },
    { key: 'ai_analysis', label: 'AI Analysis' },
    { key: 'static_analysis', label: 'Static Analysis' },
    { key: 'comparing', label: 'Comparing' },
    { key: 'scoring', label: 'Scoring' },
    { key: 'report_ready', label: 'Report Ready' },
];

function getStepIndex(status: string): number {
    const idx = PIPELINE_STEPS.findIndex(s => s.key === status);
    return idx >= 0 ? idx : 0;
}

export default function ProcessingPage() {
    const params = useParams();
    const router = useRouter();
    const { user, token, loading: authLoading } = useAuth();
    const [evaluation, setEvaluation] = useState<Evaluation | null>(null);

    const evalId = params.id as string;

    useEffect(() => {
        if (!authLoading && !user) router.push('/login');
    }, [user, authLoading, router]);

    useEffect(() => {
        if (!token || !evalId) return;
        const poll = async () => {
            try {
                const ev = await evaluations.get(evalId, token);
                setEvaluation(ev);
                if (ev.status === 'report_ready') setTimeout(() => router.push(`/results/${evalId}`), 1000);
            } catch { /* ignore */ }
        };
        poll();
        const interval = setInterval(poll, 3000);
        return () => clearInterval(interval);
    }, [token, evalId, router]);

    if (authLoading || !user) return null;

    const currentStep = evaluation ? getStepIndex(evaluation.status) : 0;
    const isFailed = evaluation?.status === 'failed' || evaluation?.status === 'timeout';

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-3">
                    <Link href="/dashboard" className="btn-ghost text-sm">← Dashboard</Link>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Processing</span>
                </div>
            </nav>

            <div className="max-w-lg mx-auto px-6 py-16 page-enter">
                <div className="text-center mb-12">
                    <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                        {isFailed ? 'Evaluation Failed' : evaluation?.status === 'report_ready' ? 'Report Ready' : 'Processing…'}
                    </h1>
                    {evaluation && (
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>{evaluation.ai_provider} / {evaluation.ai_model}</p>
                    )}
                </div>

                {isFailed && evaluation?.error_message && (
                    <div className="card p-4 mb-8">
                        <p className="text-xs font-medium mb-1" style={{ color: 'var(--danger)' }}>Error</p>
                        <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>{evaluation.error_message}</p>
                    </div>
                )}

                {/* Pipeline */}
                <div className="card p-6">
                    <div className="space-y-0">
                        {PIPELINE_STEPS.map((step, i) => {
                            const isDone = i < currentStep || evaluation?.status === 'report_ready';
                            const isActive = i === currentStep && !isFailed && evaluation?.status !== 'report_ready';

                            return (
                                <div key={step.key} className="flex items-center gap-3 py-3" style={{ borderBottom: i < PIPELINE_STEPS.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
                                    <div
                                        className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-medium flex-shrink-0"
                                        style={{
                                            background: isDone ? 'var(--accent-soft)' : isActive ? 'var(--bg-tertiary)' : 'transparent',
                                            color: isDone ? 'var(--accent)' : isActive ? 'var(--text-primary)' : 'var(--text-tertiary)',
                                            border: isDone || isActive ? 'none' : '1px solid var(--border-color)',
                                        }}
                                    >
                                        {isDone ? '✓' : i + 1}
                                    </div>
                                    <span className="text-sm" style={{ color: isDone ? 'var(--accent)' : isActive ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                                        {step.label}
                                    </span>
                                    {isActive && (
                                        <div className="flex gap-1 ml-auto">
                                            <div className="w-1 h-1 rounded-full animate-pulse" style={{ background: 'var(--text-primary)', animationDelay: '0ms' }} />
                                            <div className="w-1 h-1 rounded-full animate-pulse" style={{ background: 'var(--text-primary)', animationDelay: '200ms' }} />
                                            <div className="w-1 h-1 rounded-full animate-pulse" style={{ background: 'var(--text-primary)', animationDelay: '400ms' }} />
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {evaluation?.status === 'report_ready' && (
                    <div className="mt-6 text-center">
                        <Link href={`/results/${evalId}`} className="btn-primary">View Results →</Link>
                    </div>
                )}
            </div>
        </div>
    );
}
