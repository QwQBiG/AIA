import Database from 'better-sqlite3';
import * as fs from 'fs';
import * as path from 'path';

export interface DatabaseStatus {
  initialized: boolean;
  version: string;
  path: string;
}

export interface Migration {
  version: string;
  name: string;
  up: string;
  down?: string;
}

/**
 * Manages SQLite database initialization and migrations
 */
export class DatabaseInitializer {
  private dbPath: string;
  private db: Database.Database | null = null;

  constructor(userDataPath: string) {
    this.dbPath = path.join(userDataPath, 'data', 'ai-vtuber.db');
  }

  /**
   * Get the database file path
   */
  getDbPath(): string {
    return this.dbPath;
  }

  /**
   * Initialize the database
   * Creates the database file and required tables
   */
  async initialize(): Promise<void> {
    // Ensure directory exists
    const dir = path.dirname(this.dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Open database connection
    this.db = new Database(this.dbPath);
    
    // Enable WAL mode for better performance
    this.db.pragma('journal_mode = WAL');
    
    // Create migrations table if not exists
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create core schema tables
    this.createCoreTables();
  }

  /**
   * Create core application tables
   */
  private createCoreTables(): void {
    if (!this.db) {
      throw new Error('Database not initialized');
    }

    // Memory/conversation history table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        content TEXT NOT NULL,
        embedding BLOB,
        metadata TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Chat messages table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        username TEXT NOT NULL,
        message TEXT NOT NULL,
        processed INTEGER DEFAULT 0,
        response TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Settings table for runtime configuration
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create indexes
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
      CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
      CREATE INDEX IF NOT EXISTS idx_chat_platform ON chat_messages(platform);
      CREATE INDEX IF NOT EXISTS idx_chat_processed ON chat_messages(processed);
    `);
  }

  /**
   * Run pending database migrations
   */
  async runMigrations(): Promise<void> {
    if (!this.db) {
      await this.initialize();
    }

    const migrations = this.getMigrations();
    const appliedVersions = this.getAppliedMigrations();

    for (const migration of migrations) {
      if (!appliedVersions.includes(migration.version)) {
        console.log(`Applying migration ${migration.version}: ${migration.name}`);
        
        this.db!.transaction(() => {
          this.db!.exec(migration.up);
          this.db!.prepare(
            'INSERT INTO migrations (version, name) VALUES (?, ?)'
          ).run(migration.version, migration.name);
        })();
      }
    }
  }

  /**
   * Get list of applied migration versions
   */
  private getAppliedMigrations(): string[] {
    if (!this.db) {
      return [];
    }

    const rows = this.db.prepare(
      'SELECT version FROM migrations ORDER BY version'
    ).all() as { version: string }[];

    return rows.map(row => row.version);
  }

  /**
   * Get all available migrations
   */
  private getMigrations(): Migration[] {
    return [
      {
        version: '001',
        name: 'initial_schema',
        up: `
          -- Initial schema is created in createCoreTables
          SELECT 1;
        `,
      },
      {
        version: '002',
        name: 'add_persona_table',
        up: `
          CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT,
            voice_id TEXT,
            avatar_url TEXT,
            is_active INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
          );
        `,
      },
      {
        version: '003',
        name: 'add_stream_sessions',
        up: `
          CREATE TABLE IF NOT EXISTS stream_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME,
            message_count INTEGER DEFAULT 0,
            metadata TEXT
          );
        `,
      },
    ];
  }

  /**
   * Check if database is initialized
   */
  isInitialized(): boolean {
    if (!fs.existsSync(this.dbPath)) {
      return false;
    }

    try {
      const db = new Database(this.dbPath, { readonly: true });
      const result = db.prepare(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
      ).get();
      db.close();
      return result !== undefined;
    } catch {
      return false;
    }
  }

  /**
   * Get current database version
   */
  getVersion(): string {
    if (!this.isInitialized()) {
      return '0';
    }

    try {
      const db = new Database(this.dbPath, { readonly: true });
      const result = db.prepare(
        'SELECT version FROM migrations ORDER BY version DESC LIMIT 1'
      ).get() as { version: string } | undefined;
      db.close();
      return result?.version ?? '0';
    } catch {
      return '0';
    }
  }

  /**
   * Get database status
   */
  getStatus(): DatabaseStatus {
    return {
      initialized: this.isInitialized(),
      version: this.getVersion(),
      path: this.dbPath,
    };
  }

  /**
   * Close database connection
   */
  close(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }
}

// Singleton factory
export function createDatabaseInitializer(userDataPath: string): DatabaseInitializer {
  return new DatabaseInitializer(userDataPath);
}
