import React, { useState } from 'react';
import { useQuery } from '../hooks/useQuery';

export function DataLab() {
    const [query, setQuery] = useState('SELECT * FROM main_dataset_final LIMIT 50');
    const [activeQuery, setActiveQuery] = useState(query);
    
    const { data, isLoading, error } = useQuery(activeQuery);

    const handleRunQuery = () => {
        setActiveQuery(query);
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '1rem' }}>
            <header>
                <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>Data Lab</h1>
                <p style={{ color: 'var(--text-muted)' }}>Write raw DuckDB SQL queries against the dataset in your browser.</p>
            </header>

            <div className="glass-panel" style={{ padding: '1.5rem', flexShrink: 0 }}>
                <textarea 
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{ 
                        width: '100%', 
                        height: '100px', 
                        background: 'var(--bg-main)', 
                        color: 'var(--text-main)',
                        border: '1px solid var(--border-light)',
                        borderRadius: '6px',
                        padding: '1rem',
                        fontFamily: 'monospace',
                        resize: 'vertical',
                        marginBottom: '1rem'
                    }}
                />
                <button className="btn-primary" onClick={handleRunQuery}>Run Query</button>
            </div>

            {error && (
                <div className="glass-panel" style={{ padding: '1rem', color: 'var(--accent-error)', borderColor: 'var(--accent-error)' }}>
                    {error.message}
                </div>
            )}

            <div className="glass-panel" style={{ flex: 1, overflow: 'auto', padding: '0' }}>
                {isLoading ? (
                    <div style={{ padding: '2rem' }}>Running query...</div>
                ) : data && data.length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-panel-solid)', zIndex: 1 }}>
                            <tr>
                                {Object.keys(data[0]).map(key => (
                                    <th key={key} style={{ padding: '0.75rem 1rem', textAlign: 'left', borderBottom: '1px solid var(--border-light)', whiteSpace: 'nowrap', color: 'var(--uct-blue)' }}>
                                        {key}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((row, i) => (
                                <tr key={i}>
                                    {Object.values(row).map((val: any, j) => (
                                        <td key={j} style={{ padding: '0.5rem 1rem', borderBottom: '1px solid var(--border-light)', whiteSpace: 'nowrap', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {String(val)}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <div style={{ padding: '2rem' }}>No results.</div>
                )}
            </div>
        </div>
    );
}
