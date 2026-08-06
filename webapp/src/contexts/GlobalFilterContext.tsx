import React, { createContext, useContext, useState } from 'react';

export const GlobalFilterContext = createContext({
    faculty: 'All',
    setFaculty: (f: string) => {}
});

export const GlobalFilterProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
    const [faculty, setFaculty] = useState('All');
    return (
        <GlobalFilterContext.Provider value={{ faculty, setFaculty }}>
            {children}
        </GlobalFilterContext.Provider>
    );
};

export const useGlobalFilter = () => useContext(GlobalFilterContext);
