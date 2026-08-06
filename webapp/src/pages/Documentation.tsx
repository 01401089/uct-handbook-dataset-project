import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function Documentation() {
    const [content, setContent] = useState('Loading documentation...');
    const [selectedDoc, setSelectedDoc] = useState('USER-MANUAL.md');

    const docs = [
        'USER-MANUAL.md',
        'REPLICATION.md',
        'FINAL-DATASET-METHOD.md',
        'commerce-review-and-proposal.md'
    ];

    useEffect(() => {
        fetch(`/docs/${selectedDoc}`)
            .then(res => res.text())
            .then(text => setContent(text))
            .catch(err => setContent(`Failed to load ${selectedDoc}: ${err.message}`));
    }, [selectedDoc]);

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', gap: '2rem', height: '100%' }}>
            <div className="glass-panel" style={{ padding: '1.5rem', alignSelf: 'start', position: 'sticky', top: 0 }}>
                <h3 style={{ marginBottom: '1.5rem' }}>Documentation Hub</h3>
                <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {docs.map(doc => (
                        <button
                            key={doc}
                            onClick={() => setSelectedDoc(doc)}
                            style={{
                                textAlign: 'left',
                                padding: '0.75rem 1rem',
                                background: selectedDoc === doc ? 'var(--uct-blue)' : 'transparent',
                                color: selectedDoc === doc ? '#fff' : 'var(--text-main)',
                                border: '1px solid',
                                borderColor: selectedDoc === doc ? 'var(--uct-blue)' : 'var(--border-light)',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '0.9rem'
                            }}
                        >
                            {doc.replace('.md', '')}
                        </button>
                    ))}
                </nav>
            </div>

            <div className="glass-panel" style={{ padding: '2.5rem', overflowY: 'auto' }}>
                <div style={{ maxWidth: '800px', margin: '0 auto' }}>
                    <div className="markdown-body">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                                table: ({node, ...props}) => (
                                    <div className="markdown-table-wrapper">
                                        <table {...props} />
                                    </div>
                                )
                            }}
                        >
                            {content}
                        </ReactMarkdown>
                    </div>
                </div>
            </div>
        </div>
    );
}
