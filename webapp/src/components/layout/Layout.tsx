import React from 'react';
import { Sidebar } from './Sidebar';
import { Outlet } from 'react-router-dom';

export function Layout() {
    return (
        <div className="app-container">
            <Sidebar />
            <main className="main-content">
                <Outlet />
            </main>
        </div>
    );
}
