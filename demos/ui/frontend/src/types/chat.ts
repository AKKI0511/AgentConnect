export type MessageType = 'error' | 'text' | 'response' | 'info' | 'system' | 'stop' | 'cooldown' | 'cleanup' | 'ping';
export type SessionType = 'human_agent' | 'agent_agent';

export interface WebSocketMessage {
    type: MessageType;
    content: string;
    sender?: string;
    receiver?: string;
    timestamp?: string;
    metadata?: Record<string, any>;
}

export interface ChatMessage {
    content: string;
    sender: string;
    receiver: string;
    timestamp: string;
    type: MessageType;
    metadata?: Record<string, any>;
}

export interface Provider {
    name: string;
    models: string[];
    default_model: string;
}

export interface AgentConfigRequest {
    provider: string;
    model?: string;
    capabilities?: string[];
    personality?: string;
    metadata?: Record<string, any>;
}

export interface CreateSessionRequest {
    session_type: SessionType;
    agents: Record<string, AgentConfigRequest>;
    interaction_modes?: string[];
    metadata?: Record<string, any>;
}

export interface AgentMetadata {
    agent_id: string;
    provider: string;
    model: string;
    capabilities: string[];
    personality?: string;
    status: string;
}

export interface SessionResponse {
    session_id: string;
    type: string;
    created_at: string;
    status: string;
    session_type: SessionType;
    agents: Record<string, AgentMetadata>;
    metadata?: Record<string, any>;
}

export interface ChatSession {
    session_id: string;
    type: string;
    created_at: string;
    status: string;
    session_type: SessionType;
    agents: Record<string, AgentMetadata>;
    metadata?: Record<string, any>;
    messages: ChatMessage[];
}

export interface AgentStatus {
    agent_id: string;
    agent_type: string;
    name?: string;
    status: 'active' | 'inactive' | 'cooldown';
    last_active: string;
    capabilities: string[];
    interaction_modes: string[];
    owner_id: string;
    is_running: boolean;
    message_count: number;
    metadata: {
        provider?: string;
        model?: string;
        cooldown_until?: string | null;
        active_conversations?: number;
        total_messages_processed?: number;
    };
} 