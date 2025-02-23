import { config } from '../config/env';
import { authService } from './auth';
import { CreateSessionRequest, SessionResponse, Provider, AgentStatus } from '../types/chat';


class ApiService {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    private async fetchWithAuth<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const token = authService.getAccessToken();
        if (!token) {
            throw new Error('No authentication token available');
        }

        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            ...options,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            if (response.status === 401) {
                authService.logout();
                throw new Error('Authentication expired');
            }
            throw new Error(`API request failed: ${response.statusText}`);
        }

        return response.json();
    }

    // Chat Sessions
    async createSession(config: CreateSessionRequest): Promise<SessionResponse> {
        return this.fetchWithAuth<SessionResponse>('/chat/sessions/create', {
            method: 'POST',
            body: JSON.stringify(config),
        });
    }

    async getSession(sessionId: string): Promise<SessionResponse> {
        return this.fetchWithAuth<SessionResponse>(`/chat/sessions/${sessionId}`);
    }

    async deleteSession(sessionId: string): Promise<void> {
        await this.fetchWithAuth<void>(`/chat/sessions/${sessionId}`, {
            method: 'DELETE',
        });
    }

    // Providers
    async getProviders(): Promise<Record<string, Provider>> {
        const res = await this.fetchWithAuth<Record<string, Provider>>('/chat/providers');
        console.log(res);
        return res;
    }

    // Agents
    async registerAgent(config: {
        name: string;
        provider: string;
        model?: string;
        capabilities?: string[];
        interaction_modes?: string[];
        personality?: string;
        metadata?: Record<string, any>;
    }): Promise<{ agent_id: string; status: string }> {
        return this.fetchWithAuth<{ agent_id: string; status: string }>('/agents/register', {
            method: 'POST',
            body: JSON.stringify(config),
        });
    }

    async unregisterAgent(agentId: string): Promise<{ status: string }> {
        return this.fetchWithAuth<{ status: string }>(`/agents/${agentId}`, {
            method: 'DELETE',
        });
    }

    async listAgents(): Promise<{
        agents: AgentStatus[];
        timestamp: string;
        total_count: number;
        user_owned_count: number;
    }> {
        return this.fetchWithAuth<{
            agents: AgentStatus[];
            timestamp: string;
            total_count: number;
            user_owned_count: number;
        }>('/agents/list');
    }

    async getAgentStatus(agentId: string): Promise<AgentStatus> {
        return this.fetchWithAuth<AgentStatus>(`/agents/status/${agentId}`);
    }

    async getAgentCapabilities(agentId: string): Promise<{
        agent_id: string;
        agent_type: string;
        capabilities: string[];
        interaction_modes: string[];
        personality?: string;
        owner_id: string;
        timestamp: string;
    }> {
        return this.fetchWithAuth<{
            agent_id: string;
            agent_type: string;
            capabilities: string[];
            interaction_modes: string[];
            personality?: string;
            owner_id: string;
            timestamp: string;
        }>(`/agents/${agentId}/capabilities`);
    }

    async sendAgentMessage(agentId: string, message: {
        receiver_id: string;
        content: string;
        message_type: string;
        structured_data?: Record<string, any>;
        metadata?: Record<string, any>;
    }): Promise<{
        status: string;
        message_id: string;
        sender: string;
        receiver: string;
        timestamp: string;
    }> {
        return this.fetchWithAuth<{
            status: string;
            message_id: string;
            sender: string;
            receiver: string;
            timestamp: string;
        }>(`/agents/${agentId}/message`, {
            method: 'POST',
            body: JSON.stringify(message),
        });
    }

    getAccessToken(): string | null {
        return authService.getAccessToken();
    }
}

export const apiService = new ApiService(config.api.baseUrl);
export type { CreateSessionRequest }; 