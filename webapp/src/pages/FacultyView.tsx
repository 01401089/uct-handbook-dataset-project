import React, { useMemo, useState } from 'react';
import { useQuery } from '../hooks/useQuery';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer } from 'recharts';
import { useGlobalFilter } from '../contexts/GlobalFilterContext';

export function FacultyView() {
    const { faculty } = useGlobalFilter();
    const [searchQuery, setSearchQuery] = useState('');
    
    // We fetch all records for the selected faculty grouped by plan and year
    // We sum credits and real_cost to get the total per plan per year.
    const queryStr = faculty !== 'All' ? `
        SELECT 
            plan_code,
            specialisation,
            degree_abbrev,
            year,
            SUM(TRY_CAST(final_credits AS DOUBLE)) as total_credits,
            SUM(real_cost_2025) as real_cost
        FROM v_ideal_student_summary_real
        WHERE faculty = '${faculty}'
        GROUP BY plan_code, specialisation, degree_abbrev, year
        ORDER BY plan_code, year ASC
    ` : '';

    const { data: rawData, isLoading } = useQuery(queryStr);

    // Transform flat data into nested structure for small multiples
    const plans = useMemo(() => {
        if (!rawData) return [];
        
        const map = new Map<string, any>();
        rawData.forEach((row: any) => {
            if (!map.has(row.plan_code)) {
                map.set(row.plan_code, {
                    plan_code: row.plan_code,
                    specialisation: row.specialisation,
                    degree_abbrev: row.degree_abbrev,
                    trend: [],
                    kpi2025: { credits: null, cost: null },
                    kpi2021: { credits: null, cost: null }
                });
            }
            
            const plan = map.get(row.plan_code);
            plan.trend.push({
                year: row.year,
                credits: row.total_credits,
                cost: row.real_cost
            });
            
            if (row.year === '2025') {
                plan.kpi2025.credits = row.total_credits;
                plan.kpi2025.cost = row.real_cost;
            }
            if (row.year === '2021') {
                plan.kpi2021.credits = row.total_credits;
                plan.kpi2021.cost = row.real_cost;
            }
        });
        
        // Sort by the first numeric block found in the plan code (e.g., CB002 -> 2, CB011 -> 11)
        // If numbers are the same, fallback to specialisation alphabetical sort
        return Array.from(map.values()).sort((a, b) => {
            const extractNum = (code: string) => {
                const match = code.match(/\d+/);
                return match ? parseInt(match[0], 10) : 9999;
            };
            
            const numA = extractNum(a.plan_code || '');
            const numB = extractNum(b.plan_code || '');
            
            if (numA !== numB) {
                return numA - numB;
            }
            
            const specA = a.specialisation || '';
            const specB = b.specialisation || '';
            return specA.localeCompare(specB);
        });
    }, [rawData]);

    const filteredPlans = useMemo(() => {
        if (!searchQuery) return plans;
        const lowerQuery = searchQuery.toLowerCase();
        return plans.filter(p => 
            (p.plan_code || '').toLowerCase().includes(lowerQuery) || 
            (p.specialisation || '').toLowerCase().includes(lowerQuery)
        );
    }, [plans, searchQuery]);

    if (faculty === 'All') {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', flexDirection: 'column' }}>
                <h2 style={{ marginBottom: '1rem', color: 'var(--uct-blue)' }}>Faculty Deep Dive</h2>
                <p style={{ color: 'var(--text-muted)' }}>Please select a specific faculty from the global filter in the sidebar to view small multiples.</p>
            </div>
        );
    }

    return (
        <div>
            <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>{faculty} Deep Dive</h1>
                    <p style={{ color: 'var(--text-muted)' }}>Small multiples showing 2021-2026 trends across all specialisations based on an <strong>'Ideal Student'</strong> path (the minimum-credit, minimum-time trajectory satisfying all handbook requirements). Percentage badges indicate the net change from 2021 to 2025.</p>
                </div>
                <div style={{ minWidth: '300px', flex: '0 1 auto' }}>
                    <input 
                        type="text" 
                        placeholder="Filter by plan code (e.g. CB001)..." 
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                            width: '100%',
                            padding: '0.75rem 1rem',
                            borderRadius: '8px',
                            border: '1px solid var(--border-light)',
                            backgroundColor: 'var(--bg-panel-solid)',
                            color: 'var(--text-bright)',
                            outline: 'none',
                            fontSize: '0.9rem'
                        }}
                    />
                </div>
            </header>

            {isLoading ? (
                <div>Loading specialisations...</div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem', paddingBottom: '2rem' }}>
                    {filteredPlans.map(plan => {
                        const creditDeltaPct = plan.kpi2025.credits && plan.kpi2021.credits ? ((plan.kpi2025.credits - plan.kpi2021.credits) / plan.kpi2021.credits) * 100 : null;
                        const costDeltaPct = plan.kpi2025.cost && plan.kpi2021.cost ? ((plan.kpi2025.cost - plan.kpi2021.cost) / plan.kpi2021.cost) * 100 : null;
                        
                        return (
                        <div key={plan.plan_code} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <div style={{ height: '70px', overflow: 'hidden' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{plan.plan_code}</div>
                                <h4 style={{ margin: 0, lineHeight: 1.2, fontSize: '1.1rem', color: 'var(--text-bright)' }}>{plan.degree_abbrev}</h4>
                                <div style={{ fontSize: '0.9rem', color: 'var(--accent-teal)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={plan.specialisation}>{plan.specialisation}</div>
                            </div>
                            
                            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border-light)', borderBottom: '1px solid var(--border-light)', padding: '0.75rem 0' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>2025 Credits</div>
                                    <div style={{ fontWeight: 'bold', color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        {plan.kpi2025.credits || 'N/A'}
                                        {creditDeltaPct !== null && creditDeltaPct !== 0 && (
                                            <span title="Net change from 2021 to 2025" style={{ fontSize: '0.75rem', padding: '0.1rem 0.3rem', borderRadius: '4px', backgroundColor: creditDeltaPct > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)', color: creditDeltaPct > 0 ? '#EF4444' : '#10B981', cursor: 'help' }}>
                                                {creditDeltaPct > 0 ? '+' : ''}{creditDeltaPct.toFixed(1)}%
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>2025 Cost (ZAR)</div>
                                    <div style={{ fontWeight: 'bold', color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'flex-end' }}>
                                        {costDeltaPct !== null && costDeltaPct !== 0 && (
                                            <span title="Net change from 2021 to 2025" style={{ fontSize: '0.75rem', padding: '0.1rem 0.3rem', borderRadius: '4px', backgroundColor: costDeltaPct > 0 ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', color: costDeltaPct > 0 ? '#10B981' : '#EF4444', cursor: 'help' }}>
                                                {costDeltaPct > 0 ? '+' : ''}{costDeltaPct.toFixed(1)}%
                                            </span>
                                        )}
                                        {plan.kpi2025.cost ? `R ${plan.kpi2025.cost.toLocaleString()}` : 'N/A'}
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: '1rem', marginTop: 'auto' }}>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem', textAlign: 'center' }}>Credit Trend</div>
                                    <div style={{ height: '50px', width: '100%' }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={plan.trend}>
                                                <XAxis dataKey="year" hide />
                                                <YAxis domain={['dataMin - 10', 'dataMax + 10']} hide />
                                                <Line type="stepAfter" dataKey="credits" stroke="var(--accent-teal)" strokeWidth={2} dot={false} isAnimationActive={false} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem', textAlign: 'center' }}>Real Fee Trend</div>
                                    <div style={{ height: '50px', width: '100%' }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={plan.trend}>
                                                <XAxis dataKey="year" hide />
                                                <YAxis domain={['dataMin - 5000', 'dataMax + 5000']} hide />
                                                <Line type="monotone" dataKey="cost" stroke="var(--accent-warning)" strokeWidth={2} dot={false} isAnimationActive={false} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </div>
                        </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
