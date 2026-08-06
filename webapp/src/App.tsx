import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useDuckDB } from './hooks/useDuckDB';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';

import { FacultyView } from './pages/FacultyView';
import { CurriculumExplorer } from './pages/CurriculumExplorer';
import { DataLab } from './pages/DataLab';
import { Documentation } from './pages/Documentation';
import { GlobalFilterProvider } from './contexts/GlobalFilterContext';

function App() {
    const { isReady, error } = useDuckDB();

    if (error) {
        return (
            <div style={{ padding: '2rem', color: 'var(--accent-error)' }}>
                <h2>Failed to initialize DuckDB</h2>
                <pre>{error.message}</pre>
            </div>
        );
    }

    if (!isReady) {
        return (
            <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
                <div className="text-gradient" style={{ fontSize: '1.5rem', fontWeight: 600 }}>
                    Loading Dataset Engine (~30MB)...
                </div>
            </div>
        );
    }

    return (
        <GlobalFilterProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Layout />}>
                        <Route index element={<Dashboard />} />
                        <Route path="faculty" element={<FacultyView />} />
                        <Route path="curriculum" element={<CurriculumExplorer />} />
                        <Route path="datalab" element={<DataLab />} />
                        <Route path="docs" element={<Documentation />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </GlobalFilterProvider>
    );
}

export default App;
