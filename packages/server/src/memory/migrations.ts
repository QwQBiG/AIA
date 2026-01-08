/**
 * Database Migrations
 * 数据库迁移脚本
 */

import { Pool } from 'pg';
import { DatabaseConfig } from './types';

/**
 * 迁移脚本列表
 */
const migrations = [
  {
    version: 1,
    name: 'create_pgvector_extension',
    up: `CREATE EXTENSION IF NOT EXISTS vector;`,
    down: `DROP EXTENSION IF EXISTS vector;`,
  },
  {
    version: 2,
    name: 'create_memories_table',
    up: `
      CREATE TABLE IF NOT EXISTS memories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content TEXT NOT NULL,
        type VARCHAR(50) NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        embedding vector(1536),
        participants TEXT[],
        metadata JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );
      
      CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
    `,
    down: `DROP TABLE IF EXISTS memories;`,
  },
  {
    version: 3,
    name: 'create_embedding_index',
    up: `
      CREATE INDEX IF NOT EXISTS idx_memories_embedding 
      ON memories USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
    `,
    down: `DROP INDEX IF EXISTS idx_memories_embedding;`,
  },
  {
    version: 4,
    name: 'create_migrations_table',
    up: `
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );
    `,
    down: `DROP TABLE IF EXISTS schema_migrations;`,
  },
];

/**
 * 运行数据库迁移
 */
export async function runMigrations(config: DatabaseConfig): Promise<void> {
  const pool = new Pool({
    host: config.host,
    port: config.port,
    database: config.database,
    user: config.user,
    password: config.password,
    ssl: config.ssl ? { rejectUnauthorized: false } : undefined,
  });

  try {
    // 首先创建迁移表（如果不存在）
    await pool.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      );
    `);

    // 获取已应用的迁移版本
    const result = await pool.query('SELECT version FROM schema_migrations ORDER BY version');
    const appliedVersions = new Set(result.rows.map((row) => row.version));

    // 运行未应用的迁移
    for (const migration of migrations) {
      if (!appliedVersions.has(migration.version)) {
        console.log(`Running migration ${migration.version}: ${migration.name}`);
        await pool.query(migration.up);
        await pool.query(
          'INSERT INTO schema_migrations (version, name) VALUES ($1, $2)',
          [migration.version, migration.name]
        );
        console.log(`Migration ${migration.version} completed`);
      }
    }

    console.log('All migrations completed successfully');
  } finally {
    await pool.end();
  }
}

/**
 * 回滚最后一个迁移
 */
export async function rollbackMigration(config: DatabaseConfig): Promise<void> {
  const pool = new Pool({
    host: config.host,
    port: config.port,
    database: config.database,
    user: config.user,
    password: config.password,
    ssl: config.ssl ? { rejectUnauthorized: false } : undefined,
  });

  try {
    const result = await pool.query(
      'SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1'
    );

    if (result.rows.length === 0) {
      console.log('No migrations to rollback');
      return;
    }

    const lastVersion = result.rows[0].version;
    const migration = migrations.find((m) => m.version === lastVersion);

    if (migration) {
      console.log(`Rolling back migration ${migration.version}: ${migration.name}`);
      await pool.query(migration.down);
      await pool.query('DELETE FROM schema_migrations WHERE version = $1', [lastVersion]);
      console.log(`Rollback of migration ${migration.version} completed`);
    }
  } finally {
    await pool.end();
  }
}

/**
 * 获取迁移状态
 */
export async function getMigrationStatus(config: DatabaseConfig): Promise<{
  applied: number[];
  pending: number[];
}> {
  const pool = new Pool({
    host: config.host,
    port: config.port,
    database: config.database,
    user: config.user,
    password: config.password,
    ssl: config.ssl ? { rejectUnauthorized: false } : undefined,
  });

  try {
    // 检查迁移表是否存在
    const tableCheck = await pool.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'schema_migrations'
      );
    `);

    if (!tableCheck.rows[0].exists) {
      return {
        applied: [],
        pending: migrations.map((m) => m.version),
      };
    }

    const result = await pool.query('SELECT version FROM schema_migrations ORDER BY version');
    const appliedVersions = result.rows.map((row) => row.version);
    const pendingVersions = migrations
      .filter((m) => !appliedVersions.includes(m.version))
      .map((m) => m.version);

    return {
      applied: appliedVersions,
      pending: pendingVersions,
    };
  } finally {
    await pool.end();
  }
}
