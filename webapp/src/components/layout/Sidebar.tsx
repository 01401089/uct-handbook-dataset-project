import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Library, BookOpen, Database, FileText, Filter } from 'lucide-react';
import { useGlobalFilter } from '../../contexts/GlobalFilterContext';
import { useQuery } from '../../hooks/useQuery';

export function Sidebar() {
    const { faculty, setFaculty } = useGlobalFilter();
    const { data: faculties } = useQuery(`SELECT DISTINCT faculty FROM ideal_student_summary_final WHERE faculty IS NOT NULL ORDER BY faculty`);

    const navItems = [
        { path: '/', icon: <LayoutDashboard size={20} />, label: 'Dashboard' },
        { path: '/faculty', icon: <Library size={20} />, label: 'Faculty Deep Dive' },
        { path: '/curriculum', icon: <BookOpen size={20} />, label: 'Curriculum Explorer' },
        { path: '/datalab', icon: <Database size={20} />, label: 'Data Lab' },
        { path: '/docs', icon: <FileText size={20} />, label: 'Documentation' },
    ];

    return (
        <aside style={{ width: '260px', padding: '1.5rem', borderRight: '1px solid var(--border-light)', backgroundColor: 'var(--bg-panel-solid)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: '2rem' }}>
                <h2 className="text-gradient-uct" style={{ margin: 0, fontSize: '1.2rem', lineHeight: '1.3' }}>Dataset from UCT Handbooks</h2>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Credit Load & Fees Explorer</div>
            </div>
            
            <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        style={({ isActive }) => ({
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.75rem',
                            padding: '0.75rem 1rem',
                            borderRadius: '8px',
                            color: isActive ? 'var(--uct-blue)' : 'var(--text-main)',
                            backgroundColor: isActive ? 'rgba(0, 154, 218, 0.1)' : 'transparent',
                            textDecoration: 'none',
                            fontWeight: isActive ? 600 : 400,
                            transition: 'all 0.2s ease'
                        })}
                    >
                        {item.icon}
                        <span>{item.label}</span>
                    </NavLink>
                ))}
            </nav>

            <div style={{ marginTop: 'auto', paddingTop: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    <Filter size={16} /> Global Filters
                </div>
                <select 
                    value={faculty} 
                    onChange={e => setFaculty(e.target.value)}
                    style={{ width: '100%', padding: '0.75rem', borderRadius: '6px', background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-light)' }}
                >
                    <option value="All">All Faculties</option>
                    {faculties?.map(f => (
                        <option key={f.faculty} value={f.faculty}>{f.faculty}</option>
                    ))}
                </select>
            </div>
        </aside>
    );
}
