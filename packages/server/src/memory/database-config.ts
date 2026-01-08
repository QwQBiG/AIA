/**
 * Database Configuration
 * 数据库配置模块
 */

import { DatabaseConfig } from './types';

/**
 * 从环境变量获取数据库配置
 */
export function getDatabaseConfig(): DatabaseConfig {
  return {
    host: process.env.POSTGRES_HOST || 'localhost',
    port: parseInt(process.env.POSTGRES_PORT || '5432', 10),
    database: process.env.POSTGRES_DATABASE || 'digital_human',
    user: process.env.POSTGRES_USER || 'postgres',
    password: process.env.POSTGRES_PASSWORD || '',
    ssl: process.env.POSTGRES_SSL === 'true',
  };
}

/**
 * 获取数据库连接字符串
 */
export function getConnectionString(config: DatabaseConfig): string {
  const { host, port, database, user, password, ssl } = config;
  const sslParam = ssl ? '?sslmode=require' : '';
  return `postgresql://${user}:${password}@${host}:${port}/${database}${sslParam}`;
}
