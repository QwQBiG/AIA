/**
 * Application configuration types for AI VTuber Digital Human
 */

export type LLMProvider = 'ollama' | 'koboldcpp' | 'openai' | 'anthropic';
export type TTSProvider = 'elevenlabs' | 'azure' | 'vits' | 'gpt-sovits';

export interface DatabaseConfig {
  path: string;
}

export interface LLMConfig {
  provider: LLMProvider;
  ollamaEndpoint?: string;
  ollamaModel?: string;
  koboldcppEndpoint?: string;
  openaiApiKey?: string;
  openaiModel?: string;
  anthropicApiKey?: string;
  anthropicModel?: string;
}

export interface TTSConfig {
  provider: TTSProvider;
  apiKey?: string;
  endpoint?: string;
  voiceId?: string;
}

export interface TwitchConfig {
  username: string;
  oauthToken: string;
  channel: string;
}

export interface YouTubeConfig {
  apiKey: string;
  liveChatId?: string;
}

export interface BilibiliConfig {
  roomId: string;
  sessdata?: string;
  biliJct?: string;
}

export interface StreamingConfig {
  twitch?: TwitchConfig;
  youtube?: YouTubeConfig;
  bilibili?: BilibiliConfig;
}

export interface AppConfig {
  database: DatabaseConfig;
  llm: LLMConfig;
  tts: TTSConfig;
  streaming: StreamingConfig;
  server?: {
    port: number;
  };
  firstRun?: boolean;
}

export const DEFAULT_CONFIG: AppConfig = {
  database: {
    path: '',  // Will be set to userData path
  },
  llm: {
    provider: 'ollama',
    ollamaEndpoint: 'http://localhost:11434',
    ollamaModel: 'llama2',
  },
  tts: {
    provider: 'vits',
  },
  streaming: {},
  server: {
    port: 3000,
  },
  firstRun: true,
};
