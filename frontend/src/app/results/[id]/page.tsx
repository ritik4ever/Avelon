'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { ThemeToggle } from '@/lib/theme-context';
import { evaluations, reports, type Evaluation, type VulnerabilityItem } from '@/lib/api';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

const SEVERITY_COLORS: Record<string, string> = {
    critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#3b82f6', info: '#6b7280',
};

const MATCH_COLORS: Record<string, string> = {
    true_positive: '#22c55e', false_positive: '#ef4444', false_negative: '#f59e0b', unmatched: '#6b7280',
};

export default function ResultsPage() {
    const params = useParams();
    const router = useRouter();
    const { user, token, loading: authLoading } = useAuth();
    const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
    const [vulns, setVulns] = useState<VulnerabilityItem[]>([]);
    const [loading, setLoading] = useState(true);

    const evalId = params.id as string;

    useEffect(() => { if (!authLoading && !user) router.push('/login'); }, [user, authLoading, router]);

    useEffect(() => {
        if (!token || !evalId) return;
        const load = async () => {
            try {
                const [ev, v] = await Promise.all([evaluations.get(evalId, token), evaluations.vulnerabilities(evalId, token)]);
                setEvaluation(ev); setVulns(v);
            } catch { }
            setLoading(false);
        };
        load();
    }, [token, evalId]);

    if (authLoading || !user || loading || !evaluation) return null;

    const aiVulns = vulns.filter(v => v.source === 'ai');
    const gtVulns = vulns.filter(v => v.source !== 'ai');
    const tp = aiVulns.filter(v => v.match_classification === 'true_positive');
    const fp = aiVulns.filter(v => v.match_classification === 'false_positive');
    const fn = gtVulns.filter(v => v.match_classification === 'false_negative');

    const pieData = [
        { name: 'True Positive', value: tp.length, color: MATCH_COLORS.true_positive },
        { name: 'False Positive', value: fp.length, color: MATCH_COLORS.false_positive },
        { name: 'Missed', value: fn.length, color: MATCH_COLORS.false_negative },
    ].filter(d => d.value > 0);

    const barData = [
        { name: 'Precision', value: (evaluation.precision_score || 0) * 100 },
        { name: 'Recall', value: (evaluation.recall_score || 0) * 100 },
        { name: 'Reliability', value: (evaluation.reliability_score || 0) * 100 },
    ];

    const radarData = [
        { metric: 'Precision', score: (evaluation.precision_score || 0) * 100 },
        { metric: 'Recall', score: (evaluation.recall_score || 0) * 100 },
        { metric: 'Low Hallucination', score: (1 - (evaluation.hallucination_rate || 0)) * 100 },
        { metric: 'Low Miss Rate', score: (1 - (evaluation.miss_rate || 0)) * 100 },
        { metric: 'Reliability', score: (evaluation.reliability_score || 0) * 100 },
    ];

    const reliabilityPct = ((evaluation.reliability_score || 0) * 100).toFixed(1);
    const tooltipStyle = { background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '12px' };

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)' }}>
            <nav className="sticky top-0 z-50" style={{ background: 'var(--bg-primary)', borderBottom: '1px solid var(--border-color)' }}>
                <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link href="/dashboard" className="btn-ghost text-sm">← Dashboard</Link>
                        <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Report</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <ThemeToggle />
                        <a href={reports.getPdfUrl(evalId)} target="_blank" className="btn-secondary text-xs">Download PDF</a>
                    </div>
                </div>
            </nav>

            <div className="max-w-6xl mx-auto px-6 py-8 page-enter">
                {/* Header */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
                    <div>
                        <h1 className="text-xl font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Reliability Report</h1>
                        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                            <span className="badge-info">{evaluation.ai_provider}</span>
                            <span>{evaluation.ai_model}</span>
                            <span>·</span>
                            <span>deterministic mode</span>
                        </div>
                    </div>
                    <div className="card p-4 text-center min-w-[100px]">
                        <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{reliabilityPct}%</div>
                        <div className="text-[10px] uppercase font-medium" style={{ color: 'var(--text-tertiary)' }}>Reliability</div>
                    </div>
                </div>

                {/* Score Cards */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
                    {[
                        { label: 'Precision', value: evaluation.precision_score },
                        { label: 'Recall', value: evaluation.recall_score },
                        { label: 'Hallucination', value: evaluation.hallucination_rate },
                        { label: 'Miss Rate', value: evaluation.miss_rate },
                        { label: 'Reliability', value: evaluation.reliability_score },
                    ].map((m) => (
                        <div key={m.label} className="card p-4 text-center">
                            <div className="text-[11px] uppercase mb-1" style={{ color: 'var(--text-tertiary)' }}>{m.label}</div>
                            <div className="text-lg font-semibold font-mono" style={{ color: 'var(--text-primary)' }}>
                                {m.value != null ? `${(m.value * 100).toFixed(1)}%` : '—'}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Charts */}
                <div className="grid md:grid-cols-3 gap-4 mb-8">
                    <div className="card p-5">
                        <h3 className="text-xs font-medium uppercase mb-4" style={{ color: 'var(--text-tertiary)' }}>Findings</h3>
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                                    {pieData.map((e, i) => <Cell key={i} fill={e.color} />)}
                                </Pie>
                                <Tooltip contentStyle={tooltipStyle} />
                            </PieChart>
                        </ResponsiveContainer>
                        <div className="flex justify-center gap-3 mt-2">
                            {pieData.map(d => (
                                <div key={d.name} className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                                    <div className="w-2 h-2 rounded-sm" style={{ background: d.color }} /> {d.name} ({d.value})
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="card p-5">
                        <h3 className="text-xs font-medium uppercase mb-4" style={{ color: 'var(--text-tertiary)' }}>Scores</h3>
                        <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={barData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                                <XAxis dataKey="name" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
                                <Tooltip contentStyle={tooltipStyle} />
                                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                    {barData.map((_, i) => <Cell key={i} fill={['#737373', '#a3a3a3', '#22c55e'][i]} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="card p-5">
                        <h3 className="text-xs font-medium uppercase mb-4" style={{ color: 'var(--text-tertiary)' }}>Radar</h3>
                        <ResponsiveContainer width="100%" height={220}>
                            <RadarChart data={radarData}>
                                <PolarGrid stroke="var(--border-color)" />
                                <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--text-tertiary)', fontSize: 9 }} />
                                <PolarRadiusAxis domain={[0, 100]} tick={false} />
                                <Radar dataKey="score" stroke="var(--text-primary)" fill="var(--text-primary)" fillOpacity={0.1} strokeWidth={1.5} />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Cost */}
                {(evaluation.token_usage_prompt || evaluation.estimated_cost_usd) && (
                    <div className="card p-5 mb-8">
                        <h3 className="text-xs font-medium uppercase mb-3" style={{ color: 'var(--text-tertiary)' }}>Usage</h3>
                        <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Prompt Tokens</div>
                                <div className="text-sm font-mono" style={{ color: 'var(--text-primary)' }}>{evaluation.token_usage_prompt?.toLocaleString() || '—'}</div>
                            </div>
                            <div>
                                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Completion</div>
                                <div className="text-sm font-mono" style={{ color: 'var(--text-primary)' }}>{evaluation.token_usage_completion?.toLocaleString() || '—'}</div>
                            </div>
                            <div>
                                <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Cost</div>
                                <div className="text-sm font-mono" style={{ color: 'var(--text-primary)' }}>${evaluation.estimated_cost_usd?.toFixed(4) || '—'}</div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Vulnerability Table */}
                <div className="card overflow-hidden">
                    <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <h3 className="text-xs font-medium uppercase" style={{ color: 'var(--text-tertiary)' }}>All Findings</h3>
                        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{vulns.length} total</span>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                                    {['Source', 'Type', 'Function', 'Line', 'Severity', 'Classification'].map(h => (
                                        <th key={h} className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {vulns.map((v) => (
                                    <tr key={v.id} className="transition-colors hover:opacity-80" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                        <td className="px-4 py-2.5"><span className={v.source === 'ai' ? 'badge-info' : 'badge-neutral'}>{v.source}</span></td>
                                        <td className="px-4 py-2.5 text-xs font-mono" style={{ color: 'var(--text-primary)' }}>{v.vuln_type}</td>
                                        <td className="px-4 py-2.5 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>{v.function_name || '—'}</td>
                                        <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>{v.line_number || '—'}</td>
                                        <td className="px-4 py-2.5">
                                            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ background: `${SEVERITY_COLORS[v.severity]}15`, color: SEVERITY_COLORS[v.severity] }}>{v.severity}</span>
                                        </td>
                                        <td className="px-4 py-2.5">
                                            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ background: `${MATCH_COLORS[v.match_classification] || '#6b7280'}15`, color: MATCH_COLORS[v.match_classification] || '#6b7280' }}>{v.match_classification.replace(/_/g, ' ')}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
