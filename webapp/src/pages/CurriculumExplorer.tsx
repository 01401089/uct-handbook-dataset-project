import React, { useState } from 'react';
import { useQuery } from '../hooks/useQuery';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useGlobalFilter } from '../contexts/GlobalFilterContext';

export function CurriculumExplorer() {
    const { faculty } = useGlobalFilter();
    const [searchTerm, setSearchTerm] = useState('');

    // Get the degree info
    const { data: specData } = useQuery(`
        SELECT DISTINCT plan_code, degree_abbrev, specialisation, faculty 
        FROM ideal_student_summary_final 
        WHERE (plan_code ILIKE '%${searchTerm}%' OR specialisation ILIKE '%${searchTerm}%')
        ${faculty !== 'All' ? `AND faculty = '${faculty}'` : ''}
        LIMIT 1
    `);

    const spec = specData?.[0]?.plan_code || '';
    
    // Waterfall data (we use a bar chart to simulate the cost accumulation per year)
    const { data: costWaterfall } = useQuery(spec ? `
        SELECT 
            study_year,
            final_credits,
            real_cost_2025 as cost
        FROM v_ideal_student_summary_real
        WHERE plan_code = '${spec}' AND year = '2025'
        ORDER BY study_year
    ` : '');
    
    console.log("Cost Waterfall:", costWaterfall);
    console.log("Spec:", spec);

    // Diff Data: 2024 vs 2025
    const { data: diffData } = useQuery(spec ? `
        SELECT 
            '2024' as edition,
            SUM(TRY_CAST(final_credits AS DOUBLE)) as total_credits,
            SUM(real_cost_2025) as real_cost
        FROM v_ideal_student_summary_real
        WHERE plan_code = '${spec}' AND year = '2024'
        UNION ALL
        SELECT 
            '2025' as edition,
            SUM(TRY_CAST(final_credits AS DOUBLE)) as total_credits,
            SUM(real_cost_2025) as real_cost
        FROM v_ideal_student_summary_real
        WHERE plan_code = '${spec}' AND year = '2025'
    ` : '');

    return (
        <div>
            <header style={{ marginBottom: '2rem' }}>
                <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>Curriculum Explorer</h1>
                <p style={{ color: 'var(--text-muted)' }}>Zoom into the Ideal Student path for a specific programme.</p>
                
                <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                    <input 
                        type="text" 
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder="Search Plan Code (e.g. CB004FTX04)"
                        style={{ padding: '0.75rem', borderRadius: '6px', border: '1px solid var(--border-light)', background: 'var(--bg-panel-solid)', color: '#fff', width: '300px' }}
                    />
                </div>
            </header>

            {specData?.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        {specData?.[0] ? (
                            <>
                                <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '0.25rem' }}>{specData[0].plan_code} | {specData[0].faculty}</div>
                                <h3 style={{ margin: 0 }}>{specData[0].degree_abbrev} - {specData[0].specialisation}</h3>
                            </>
                        ) : <div>No curriculum found matching '{searchTerm}' {faculty !== 'All' ? `in ${faculty}` : ''}</div>}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                        <div className="glass-panel" style={{ padding: '1.5rem' }}>
                            <h3 style={{ marginBottom: '1.5rem' }}>Cost Accumulation (2025 Cohort)</h3>
                            <div style={{ height: '300px' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={costWaterfall}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                                        <XAxis dataKey="study_year" stroke="var(--text-muted)" />
                                        <YAxis stroke="var(--text-muted)" tickFormatter={(v) => `R${v/1000}k`} />
                                        <Tooltip formatter={(v: any) => `R ${Number(v).toLocaleString()}`} contentStyle={{ backgroundColor: 'var(--bg-panel-solid)', border: 'none', borderRadius: '8px' }} />
                                        <Legend />
                                        <Bar dataKey="cost" fill="var(--accent-teal)" name="Cost (2025 Rands)" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className="glass-panel" style={{ padding: '1.5rem' }}>
                            <h3 style={{ marginBottom: '1.5rem' }}>Year-over-Year Delta (2024 vs 2025)</h3>
                            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr>
                                        <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '2px solid var(--border-light)' }}>Edition</th>
                                        <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '2px solid var(--border-light)' }}>Total Credits</th>
                                        <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '2px solid var(--border-light)' }}>Total Real Cost</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {diffData?.map(row => (
                                        <tr key={row.edition}>
                                            <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--border-light)' }}>{row.edition}</td>
                                            <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--border-light)' }}>{row.total_credits}</td>
                                            <td style={{ padding: '0.75rem', borderBottom: '1px solid var(--border-light)' }}>
                                                R {Number(row.real_cost || 0).toLocaleString()}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: '2rem' }}>
                    No results found for that code.
                </div>
            )}
        </div>
    );
}
