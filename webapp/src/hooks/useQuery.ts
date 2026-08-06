import { useState, useEffect } from 'react';
import { getConnection } from '../lib/duckdb';
import { Table } from 'apache-arrow';

export function useQuery<T = any>(queryStr: string) {
    const [data, setData] = useState<T[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        let isMounted = true;
        
        async function run() {
            if (!queryStr) {
                setData([]);
                setIsLoading(false);
                return;
            }
            setIsLoading(true);
            try {
                const conn = await getConnection();
                const arrowResult: any = await conn.query(queryStr);
                const rows = arrowResult.toArray().map((r: any) => r.toJSON()) as T[];
                if (isMounted) {
                    setData(rows);
                    setError(null);
                }
            } catch (err: any) {
                if (isMounted) {
                    setError(err);
                }
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        }
        
        if (queryStr) {
            run();
        }
    }, [queryStr]);

    return { data, isLoading, error };
}
