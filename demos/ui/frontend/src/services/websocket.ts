import { config } from '../config/env';
import { WebSocketMessage, MessageType } from '../types/chat';

export class WebSocketService {
    private socket: WebSocket | null = null;
    private messageHandler: ((message: WebSocketMessage) => void) | null = null;
    private heartbeatInterval: NodeJS.Timeout | null = null;
    private isConnecting: boolean = false;

    async connect(sessionId: string, token: string): Promise<void> {
        if (this.isConnecting) {
            console.log('WebSocket connection already in progress');
            return;
        }

        if (this.socket?.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        this.isConnecting = true;

        return new Promise((resolve, reject) => {
            try {
                // Cleanup any existing socket
                this.disconnect();

                const wsUrl = new URL(`${config.api.wsUrl}/chat/ws/${sessionId}`);
                wsUrl.searchParams.set('token', token);
                this.socket = new WebSocket(wsUrl.toString());

                this.socket.onopen = () => {
                    console.log('WebSocket connected');
                    this.isConnecting = false;
                    this.startHeartbeat();
                    resolve();
                };

                this.socket.onclose = () => {
                    console.log('WebSocket closed');
                    this.isConnecting = false;
                    this.stopHeartbeat();
                    this.socket = null;
                };

                this.socket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.isConnecting = false;
                    this.disconnect();
                    reject(error);
                };

                this.socket.onmessage = (event) => {
                    try {
                        const message: WebSocketMessage = JSON.parse(event.data);
                        if (message.type === 'error') {
                            console.error('Received error message:', message);
                        }
                        this.messageHandler?.(message);
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error);
                    }
                };

            } catch (error) {
                this.isConnecting = false;
                console.error('Failed to connect WebSocket:', error);
                reject(error);
            }
        });
    }

    private startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatInterval = setInterval(() => {
            if (this.socket?.readyState === WebSocket.OPEN) {
                this.sendMessage({
                    type: 'ping' as MessageType,
                    content: '',
                    timestamp: new Date().toISOString()
                });
            }
        }, 30000); // Send ping every 30 seconds
    }

    private stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    disconnect(): void {
        this.stopHeartbeat();
        if (this.socket) {
            // Only close if not already closing or closed
            if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
                this.socket.close();
            }
            this.socket = null;
        }
        this.isConnecting = false;
    }

    getSocket(): WebSocket | null {
        return this.socket;
    }

    onMessage(handler: (message: WebSocketMessage) => void): void {
        this.messageHandler = handler;
    }

    sendMessage(message: WebSocketMessage): void {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected');
            return;
        }
        this.socket.send(JSON.stringify(message));
    }

    isConnected(): boolean {
        return this.socket?.readyState === WebSocket.OPEN;
    }
}

export const wsService = new WebSocketService(); 