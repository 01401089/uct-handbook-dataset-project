import React, { useState, useEffect } from 'react';
import { useQuery } from '../hooks/useQuery';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useGlobalFilter } from '../contexts/GlobalFilterContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function Dashboard() {
    const { faculty } = useGlobalFilter();
    const facultyFilter = faculty !== 'All' ? `AND faculty = '${faculty}'` : '';
    const facultyFilterWhere = faculty !== 'All' ? `WHERE faculty = '${faculty}'` : '';

    const [projectReport, setProjectReport] = useState('Loading project report...');

    useEffect(() => {
        fetch('/docs/PROJECT-REPORT.md')
            .then(res => res.text())
            .then(text => setProjectReport(text))
            .catch(err => setProjectReport(`Failed to load project report: ${err.message}`));
    }, []);

    const { data: kpiData, isLoading: kpiLoading } = useQuery(`
        SELECT 
            COUNT(DISTINCT plan_code) as total_specialisations,
            COUNT(DISTINCT faculty) as total_faculties
        FROM v_ideal_student_summary_real
        WHERE year = '2025' ${facultyFilter}
    `);

    const { data: creditTrend } = useQuery(`
        SELECT 
            year,
            ROUND(AVG(TRY_CAST(final_credits AS DOUBLE)), 1) as avg_credits
        FROM v_ideal_student_summary_real
        WHERE final_credits IS NOT NULL AND final_credits != '' ${facultyFilter}
        GROUP BY year
        ORDER BY year ASC
    `);

    // Fee Trend Query
    const [useRealFees, setUseRealFees] = useState(true);
    const { data: feeTrend } = useQuery(`
        SELECT 
            year,
            ROUND(AVG(nominal_cost_numeric), 0) as avg_nominal_fee,
            ROUND(AVG(real_cost_2025), 0) as avg_real_fee
        FROM v_ideal_student_summary_real
        WHERE nominal_cost_numeric > 0 ${facultyFilter}
        GROUP BY year
        ORDER BY year ASC
    `);

    return (
        <div>
            <header style={{ marginBottom: '2rem' }}>
                <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>University Overview</h1>
                <p style={{ color: 'var(--text-muted)' }}>Macro-level trends across the credit re-think period (2021-2026).</p>
            </header>

            {kpiLoading ? (
                <div>Loading KPIs...</div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
                    <div className="glass-card">
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Tracked Specialisations (2025)</div>
                        <div style={{ fontSize: '2rem', fontWeight: 'bold' }}>{kpiData[0]?.total_specialisations || 0}</div>
                    </div>
                    <div className="glass-card">
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>Total Tracked Records</div>
                        <div style={{ fontSize: '2rem', fontWeight: 'bold' }}>24,536</div>
                    </div>
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <div className="glass-panel" style={{ padding: '1.5rem' }}>
                    <h3 style={{ marginBottom: '1.5rem' }}>Average Credit Load Trend</h3>
                    <div style={{ height: '300px' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={creditTrend}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                                <XAxis dataKey="year" stroke="var(--text-muted)" />
                                <YAxis stroke="var(--text-muted)" domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ backgroundColor: 'var(--bg-panel-solid)', border: 'none', borderRadius: '8px' }} />
                                <Legend />
                                <Line type="monotone" dataKey="avg_credits" name="Avg Credits" stroke="var(--accent-teal)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="glass-panel" style={{ padding: '1.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                        <h3>Fee Implication Trend</h3>
                        <button 
                            className="btn-outline" 
                            style={{ fontSize: '0.8rem', padding: '0.25rem 0.75rem' }}
                            onClick={() => setUseRealFees(!useRealFees)}
                        >
                            Toggle: {useRealFees ? 'Real (2025 Rands)' : 'Nominal (As-Printed)'}
                        </button>
                    </div>
                    
                    <div style={{ height: '300px' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={feeTrend}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                                <XAxis dataKey="year" stroke="var(--text-muted)" />
                                <YAxis stroke="var(--text-muted)" domain={['auto', 'auto']} tickFormatter={(value) => `R${value/1000}k`} />
                                <Tooltip formatter={(value: any) => `R ${value.toLocaleString()}`} contentStyle={{ backgroundColor: 'var(--bg-panel-solid)', border: 'none', borderRadius: '8px' }} />
                                <Legend />
                                <Line 
                                    type="monotone" 
                                    dataKey={useRealFees ? "avg_real_fee" : "avg_nominal_fee"} 
                                    name={useRealFees ? "Avg Fee (2025 Rands)" : "Avg Fee (Nominal)"} 
                                    stroke="var(--accent-warning)" 
                                    strokeWidth={3} 
                                    dot={{ r: 4 }} 
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            <div className="glass-panel" style={{ marginTop: '2rem', padding: '2.5rem' }}>
                <div style={{ maxWidth: '900px', margin: '0 auto' }}>
                    <div className="markdown-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {projectReport}
                        </ReactMarkdown>
                    </div>
                </div>
            </div>
        </div>
    );
}
