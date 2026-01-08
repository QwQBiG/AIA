/**
 * PostgreSQL Memory Store
 * PostgreSQL 记忆存储实现
 */

import { Pool, PoolClient } from 'pg';
import { v4 as uuidv4 } from 'uuid';
import { Memory, MemoryInput } from '@digital-human/shared';
import { DatabaseConfig, IMemoryStore, MemoryRow } from './types';

/**
 * PostgreSQL 记忆存储类
 */
export class PostgresMemoryStore implements IMemoryStore {
  private pool: Pool | null = null;
  private config: DatabaseConfig;
  private initialized = false;

  constructor(config: DatabaseConfig) {
    this.config = config;
  }

  /**
   * 初始化数据库连接池
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    this.pool = new Pool({
      host: this.config.host,
      port: this.config.port,
      database: this.config.database,
      user: this.config.user,
      password: this.config.password,
      ssl: this.config.ssl ? { rejectUnauthorized: false } : undefined,
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // 测试连接
    const client = await this.pool.connect();
    try {
      await client.query('SELECT 1');
      this.initialized = true;
    } finally {
      client.release();
    }
  }

  /**
   * 关闭数据库连接
   */
  async close(): Promise<void> {
    if (this.pool) {
      await this.pool.end();
      this.pool = null;
      this.initialized = false;
    }
  }

  /**
   * 获取连接池
   */
  private getPool(): Pool {
    if (!this.pool || !this.initialized) {
      throw new Error('PostgresMemoryStore not initialized. Call initialize() first.');
    }
    return this.pool;
  }

  /**
   * 存储记忆
   */
  async storeMemory(memory: MemoryInput, embedding: number[]): Promise<string> {
    const pool = this.getPool();
    const id = uuidv4();
    const embeddingStr = `[${embedding.join(',')}]`;

    await pool.query(
      `INSERT INTO memories (id, content, type, timestamp, embedding, participants, metadata)
       VALUES ($1, $2, $3, $4, $5::vector, $6, $7)`,
      [
        id,
        memory.content,
        memory.type,
        new Date(),
        embeddingStr,
        memory.participants || null,
        memory.metadata ? JSON.stringify(memory.metadata) : null,
      ]
    );

    return id;
  }

  /**
   * 语义搜索记忆
   */
  async searchMemories(queryEmbedding: number[], limit: number): Promise<Memory[]> {
    const pool = this.getPool();
    const embeddingStr = `[${queryEmbedding.join(',')}]`;
    const effectiveLimit = Math.min(limit, 10);

    const result = await pool.query<MemoryRow & { similarity: number }>(
      `SELECT id, content, type, timestamp, embedding, participants, metadata,
              1 - (embedding <=> $1::vector) as similarity
       FROM memories
       WHERE embedding IS NOT NULL
       ORDER BY embedding <=> $1::vector
       LIMIT $2`,
      [embeddingStr, effectiveLimit]
    );

    return result.rows.map((row) => this.rowToMemory(row, row.similarity));
  }

  /**
   * 获取最近记忆
   */
  async getRecentMemories(count: number): Promise<Memory[]> {
    const pool = this.getPool();
    const effectiveCount = Math.min(count, 50);

    const result = await pool.query<MemoryRow>(
      `SELECT id, content, type, timestamp, embedding, participants, metadata
       FROM memories
       ORDER BY timestamp DESC
       LIMIT $1`,
      [effectiveCount]
    );

    return result.rows.map((row) => this.rowToMemory(row));
  }

  /**
   * 将数据库行转换为 Memory 对象
   */
  private rowToMemory(row: MemoryRow, relevanceScore?: number): Memory {
    const memory: Memory = {
      id: row.id,
      content: row.content,
      type: row.type,
      timestamp: new Date(row.timestamp),
    };

    if (row.embedding) {
      // 解析向量字符串 "[1,2,3]" -> [1, 2, 3]
      const embeddingStr = row.embedding.replace(/[\[\]]/g, '');
      memory.embedding = embeddingStr.split(',').map(Number);
    }

    if (relevanceScore !== undefined) {
      memory.relevanceScore = relevanceScore;
    }

    return memory;
  }
}
