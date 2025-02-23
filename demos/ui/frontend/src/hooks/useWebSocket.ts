import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatSession, ChatMessage, WebSocketMessage, MessageType, SessionType } from '../types/chat';
import { wsService } from '../services/websocket';
import { apiService } from '../services/api';

interface UseWebSocketProps {
    sessionType: SessionType;
}

export const useWebSocket = ({ sessionType }: UseWebSocketProps) => {
    const [session, setSession] = useState<ChatSession | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isConnecting, setIsConnecting] = useState(false);
    const sessionRef = useRef<ChatSession | null>(null);

    // Keep session in ref for cleanup
    useEffect(() => {
        sessionRef.current = session;
    }, [session]);

    const connect = useCallback(async (sessionData: ChatSession) => {
        setIsConnecting(true);
        setError(null);
        try {
            setSession(sessionData);

            const token = apiService.getAccessToken();
            if (!token) {
                throw new Error('No authentication token available');
            }

            await wsService.connect(sessionData.session_id, token);
            wsService.onMessage(handleMessage);
        } catch (err) {
            console.error('WebSocket connection error:', err);
            setError(err instanceof Error ? err.message : 'Failed to connect');
            setSession(null);
        } finally {
            setIsConnecting(false);
        }
    }, []);

    const handleMessage = useCallback((message: WebSocketMessage) => {
        if (message.content && ['text', 'response'].includes(message.type)) {
            setSession(prev => {
                if (!prev) return null;

                if (sessionType === 'human_agent') {
                    const aiAgentId = prev.agents.ai_agent?.agent_id;
                    if (!aiAgentId) return prev;

                    const newMessage: ChatMessage = {
                        content: typeof message.content === 'object' ? JSON.stringify(message.content) : String(message.content),
                        sender: message.sender === aiAgentId ? 'assistant' : 'user',
                        receiver: message.receiver || aiAgentId,
                        timestamp: message.timestamp || new Date().toISOString(),
                        type: message.type as MessageType,
                        metadata: message.metadata
                    };
                    return {
                        ...prev,
                        messages: [...prev.messages, newMessage],
                    };
                }

                const newMessage: ChatMessage = {
                    content: typeof message.content === 'object' ? JSON.stringify(message.content) : String(message.content),
                    sender: message.sender || 'system',
                    receiver: message.receiver || 'all',
                    timestamp: message.timestamp || new Date().toISOString(),
                    type: message.type as MessageType,
                    metadata: message.metadata
                };

                return {
                    ...prev,
                    messages: [...prev.messages, newMessage],
                };
            });
        } else if (message.type === 'error') {
            console.error('Received error message:', message);
            setError(message.content ? 
                (typeof message.content === 'object' ? 
                    JSON.stringify(message.content) : 
                    String(message.content)
                ) : 'An error occurred'
            );
        }
    }, [sessionType]);

    const sendMessage = useCallback((content: string) => {
        if (!session) {
            console.error('No session available');
            return;
        }

        const message: WebSocketMessage = {
            type: 'text',
            content,
            timestamp: new Date().toISOString(),
            metadata: {
                conversation_type: sessionType
            }
        };

        wsService.sendMessage(message);

        // Only add user message to UI for human-agent chat
        if (sessionType === 'human_agent') {
            setSession(prev => {
                if (!prev) return null;
                const aiAgentId = prev.agents.ai_agent?.agent_id;
                if (!aiAgentId) return prev;

                const userMessage: ChatMessage = {
                    content,
                    sender: 'user',
                    receiver: aiAgentId,
                    timestamp: new Date().toISOString(),
                    type: 'text',
                    metadata: message.metadata
                };

                return {
                    ...prev,
                    messages: [...prev.messages, userMessage],
                };
            });
        }
    }, [session, sessionType]);

    const disconnect = useCallback(() => {
        wsService.disconnect();
        setSession(null);
        setError(null);
        setIsConnecting(false);
    }, []);

    // Cleanup effect
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    return {
        session,
        error,
        isConnecting,
        connect,
        sendMessage,
        disconnect
    };
}; 