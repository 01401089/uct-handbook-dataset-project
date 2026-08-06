import { useState, useEffect } from 'react';
import { initDuckDB } from '../lib/duckdb';

export function useDuckDB() {
    const [isReady, setIsReady] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        initDuckDB()
            .then(() => setIsReady(true))
            .catch((err) => setError(err));
    }, []);

    return { isReady, error };
}
