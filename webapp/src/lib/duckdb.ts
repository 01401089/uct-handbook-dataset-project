import * as duckdb from '@duckdb/duckdb-wasm';
import duckdb_wasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import mvp_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import duckdb_wasm_eh from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import eh_worker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';

const MANUAL_BUNDLES: duckdb.DuckDBBundles = {
    mvp: {
        mainModule: duckdb_wasm,
        mainWorker: mvp_worker,
    },
    eh: {
        mainModule: duckdb_wasm_eh,
        mainWorker: eh_worker,
    },
};

let db: duckdb.AsyncDuckDB | null = null;
let conn: duckdb.AsyncDuckDBConnection | null = null;
let initPromise: Promise<duckdb.AsyncDuckDB> | null = null;

export async function initDuckDB(): Promise<duckdb.AsyncDuckDB> {
    if (db) return db;
    if (initPromise) return initPromise;

    initPromise = (async () => {
        // Select a bundle based on browser checks
        const bundle = await duckdb.selectBundle(MANUAL_BUNDLES);
        
        // Instantiate the asynchronus version of DuckDB-wasm
        const worker = new Worker(bundle.mainWorker!);
        const logger = new duckdb.ConsoleLogger();
        const duckDB = new duckdb.AsyncDuckDB(logger, worker);
        await duckDB.instantiate(bundle.mainModule, bundle.pthreadWorker);
        
        db = duckDB;
        conn = await db.connect();

        await loadDataFiles();
        await createNormalizedViews();

        return db;
    })();

    return initPromise;
}

export async function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
    if (!conn) {
        await initDuckDB();
    }
    return conn!;
}

const DATA_FILES = [
    'course_fees.csv',
    'courses.csv',
    'curriculum.csv',
    'curriculum_totals.csv',
    'degree_rules.csv',
    'ideal_student_summary.csv',
    'ideal_student_summary_final.csv',
    'main_dataset.csv',
    'main_dataset_final.csv',
    'programme_fees_published.csv',
    'specialisations.csv'
];

async function loadDataFiles() {
    if (!db || !conn) return;

    for (const file of DATA_FILES) {
        const tableName = file.replace('.csv', '');
        const url = new URL(`/data/${file}`, window.location.origin).href;
        
        try {
            await db.registerFileURL(file, url, duckdb.DuckDBDataProtocol.HTTP, false);
            await conn.query(`
                CREATE TABLE ${tableName} AS 
                SELECT * FROM read_csv_auto('${file}', ALL_VARCHAR=TRUE)
            `);
            console.log(`Loaded ${tableName}`);
        } catch (error) {
            console.error(`Failed to load ${tableName} from ${url}:`, error);
        }
    }
}

async function createNormalizedViews() {
    if (!conn) return;

    // We create a multiplier mapping table
    // Let's assume an empirical 5.5% annual increase for UCT fees (approx) for this prototype,
    // or calculate it directly from course_fees if we wanted. 
    // For simplicity, we hardcode an index relative to 2025.
    // 2021 -> 2022 (e.g. 5%), 2022 -> 2023 (e.g. 5%), 2023 -> 2024 (e.g. 5%), 2024 -> 2025 (e.g. 5%)
    // Actual multipliers to convert to 2025 constant Rands:
    // 2026: 0.95 (deflate 5%)
    // 2025: 1.0
    // 2024: 1.05
    // 2023: 1.1025
    // 2022: 1.157
    // 2021: 1.215
    await conn.query(`
        CREATE TABLE fee_inflation_index (
            year VARCHAR,
            multiplier_to_2025 DOUBLE
        );
        INSERT INTO fee_inflation_index VALUES 
            ('2021', 1.215),
            ('2022', 1.157),
            ('2023', 1.1025),
            ('2024', 1.05),
            ('2025', 1.0),
            ('2026', 0.95);
    `);

    // Create a view that normalizes the ideal student summary fees
    await conn.query(`
        CREATE VIEW v_ideal_student_summary_real AS
        SELECT 
            i.*,
            TRY_CAST(i.final_fee_zar AS DOUBLE) as nominal_cost_numeric,
            TRY_CAST(i.final_fee_zar AS DOUBLE) * f.multiplier_to_2025 as real_cost_2025
        FROM ideal_student_summary_final i
        LEFT JOIN fee_inflation_index f ON i.year = f.year;
    `);

    console.log('Normalized views created.');
}
