// API Configuration
const DEFAULT_API_URL = 'http://127.0.0.1:8000/api';
const DEFAULT_WS_URL = 'ws://127.0.0.1:8000/api';

// Helper to get environment variable with fallback
const getEnvVar = (key: string, defaultValue: string): string => {
    const value = import.meta.env[key];
    return value !== undefined ? value : defaultValue;
};

export const config = {
    api: {
        baseUrl: getEnvVar('VITE_API_URL', DEFAULT_API_URL),
        wsUrl: getEnvVar('VITE_WS_URL', DEFAULT_WS_URL),
        timeout: 30000, // 30 seconds
        retryAttempts: 3,
        sessionTimeout: 3600000, // 1 hour in milliseconds
        keepAliveInterval: 30000, // 30 seconds
    },
    auth: {
        tokenKey: 'auth_token',
        tokenType: 'Bearer',
        loginEndpoint: '/auth/login',
        verifyEndpoint: '/auth/verify',
    },
    websocket: {
        reconnectAttempts: 5,
        reconnectInterval: 1000, // Start with 1 second
        pingInterval: 29000, // 29 seconds
        pongTimeout: 5000, // 5 seconds to receive pong
    },
    agent: {
        defaultProvider: getEnvVar('VITE_DEFAULT_PROVIDER', 'openai'),
        defaultModel: getEnvVar('VITE_DEFAULT_MODEL', 'gpt-3.5-turbo'),
        defaultTemperature: 0.7,
    },
    app: {
        name: 'AgentConnect',
        version: '1.0.0',
        environment: import.meta.env.MODE,
    },
} as const;

export type Config = typeof config;

// Validate configuration
const validateConfig = () => {
    const { baseUrl, wsUrl } = config.api;
    try {
        new URL(baseUrl);
        new URL(wsUrl);
    } catch (error) {
        console.error(`Invalid URL configuration:`, error);
        throw error;
    }
};

// Run validation in development
if (import.meta.env.DEV) {
    validateConfig();
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'; 