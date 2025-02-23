export enum MessageType {
    TEXT = "text",
    SYSTEM = "system",
    ERROR = "error",
    STATUS = "status"
}

export enum MessageRole {
    USER = "user",
    ASSISTANT = "assistant",
    SYSTEM = "system"
}

export interface Message {
    content: string;
    sender: string;
    type: MessageType;
    role: MessageRole;
    timestamp: string;
    metadata?: Record<string, any>;
}

export interface ChatSession {
    session_id: string;
    agent_config: Record<string, any>;
    messages: Message[];
    created_at: string;
    updated_at: string;
    metadata?: Record<string, any>;
}

export interface AgentConfig {
    provider: string;
    model: string;
    temperature: number;
    max_tokens?: number;
    stop_sequences?: string[];
    additional_params?: Record<string, any>;
}

export interface ChatConfig {
    session_id?: string;
    agent_config: AgentConfig;
    metadata?: Record<string, any>;
}

export interface ChatResponse {
    message: Message;
    session_id: string;
    status: string;
    metadata?: Record<string, any>;
}

export interface WebSocketMessage {
    type: string;
    content: string;
    timestamp: string;
    metadata?: Record<string, any>;
} 