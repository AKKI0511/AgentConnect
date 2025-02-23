import React, { useEffect, useRef, useState } from 'react';
import { ChatSession, ChatMessage as ChatMessageType } from '../types/chat';
import { ChatMessage } from './ChatMessage';

interface ChatWindowProps {
    session: ChatSession;
    onSendMessage: (content: string) => void;
    className?: string;
    showHeader?: boolean;
    isConnected?: boolean;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
    session,
    onSendMessage,
    className = '',
    showHeader = true,
    isConnected = true
}) => {
    const [message, setMessage] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [session.messages]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!message.trim() || !isConnected) return;

        onSendMessage(message.trim());
        setMessage('');
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const renderMessage = (message: ChatMessageType, index: number) => {
        // const metadata = session.metadata || {};
        const agent1Id = session.agents.agent1?.agent_id;
        const agent2Id = session.agents.agent2?.agent_id;
        const aiAgentId = session.agents.ai_agent?.agent_id;

        const isAgent1 = message.sender === agent1Id;
        const isAgent2 = message.sender === agent2Id;
        const isAiAgent = message.sender === aiAgentId;
        const isSystem = message.sender === 'system';
        const isUser = message.sender === 'user';

        // Add visual separator for different days
        const showDateSeparator = index > 0 && 
            new Date(message.timestamp).toLocaleDateString() !== 
            new Date(session.messages[index - 1].timestamp).toLocaleDateString();

        return (
            <React.Fragment key={message.timestamp}>
                {showDateSeparator && (
                    <div className="flex items-center justify-center my-6">
                        <div className="px-4 py-1 rounded-full bg-gray-700/30 backdrop-blur-sm text-xs text-gray-300 border border-gray-600/30">
                            {new Date(message.timestamp).toLocaleDateString(undefined, { 
                                weekday: 'long', 
                                year: 'numeric', 
                                month: 'long', 
                                day: 'numeric' 
                            })}
                        </div>
                    </div>
                )}
                <ChatMessage 
                    message={{
                        ...message,
                        type:  isUser ? 'text' : 
                               isSystem ? 'system' : 
                               isAiAgent ? 'response' :
                               isAgent1 ? 'text' :
                               isAgent2 ? 'response' :
                               'response'
                    }}
                    isOwnMessage={isUser}
                />
            </React.Fragment>
        );
    };

    return (
        <div className={`flex flex-col h-full max-h-[calc(100vh-4rem)] sm:max-h-[calc(100vh-8rem)] ${className}`}>
            {/* Header */}
            {showHeader && (
                <div className="flex-none p-3 sm:p-4 border-b border-gray-700/50 bg-gray-800/50 backdrop-blur-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-lg sm:text-xl font-semibold text-transparent bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-500 bg-clip-text">
                                {session.agents.agent1 && session.agents.agent2
                                    ? 'Agent Collaboration'
                                    : 'Chat Session'}
                            </h2>
                            <p className="text-xs sm:text-sm text-gray-400 mt-0.5 sm:mt-1">
                                {session.agents.ai_agent?.provider || session.agents.agent1?.provider} - {session.agents.ai_agent?.model || session.agents.agent1?.model}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3 sm:space-y-4 custom-scrollbar">
                {session.messages.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center space-y-3 sm:space-y-4">
                            <div className="text-xl sm:text-2xl font-semibold text-transparent bg-gradient-to-r from-purple-400 via-pink-300 to-purple-500 bg-clip-text">
                                Start the Conversation
                            </div>
                            <p className="text-gray-400 text-xs sm:text-sm max-w-md mx-auto px-4">
                                {session.agents.agent1 && session.agents.agent2
                                    ? "Watch as two AI agents collaborate and solve problems together."
                                    : "Begin your conversation with the AI assistant."}
                            </p>
                        </div>
                    </div>
                ) : (
                    <>
                        {session.messages.map((msg, idx) => renderMessage(msg, idx))}
                        <div ref={messagesEndRef} />
                    </>
                )}
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="flex-none p-3 sm:p-4 border-t border-gray-700/50 bg-gray-800/50 backdrop-blur-sm">
                <div className="flex gap-2 sm:gap-4">
                    <div className="relative flex-1">
                        <textarea
                            ref={inputRef}
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={isConnected ? "Type a message..." : "Reconnecting..."}
                            disabled={!isConnected}
                            className={`w-full bg-gray-900/50 text-gray-100 rounded-xl border border-gray-700/50 p-2 sm:p-3 pr-16 sm:pr-24 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 resize-none placeholder:text-gray-500 min-h-[2.25rem] sm:min-h-[2.5rem] max-h-32 transition-all duration-300 text-sm sm:text-base ${!isConnected ? 'opacity-50 cursor-not-allowed' : ''}`}
                            rows={1}
                        />
                        <div className="absolute right-2 sm:right-3 bottom-1.5 sm:bottom-2 text-[10px] sm:text-xs text-gray-400">
                            {isConnected ? 'Press Enter to send' : 'Connecting...'}
                        </div>
                    </div>
                    <button
                        type="submit"
                        disabled={!message.trim() || !isConnected}
                        className="relative group overflow-hidden rounded-xl"
                    >
                        <div className="absolute inset-0 w-3/6 bg-gradient-to-r from-purple-500/50 via-pink-400/50 to-purple-500/50 blur-lg group-hover:w-full transition-all duration-1000"></div>
                        <div className={`relative px-4 sm:px-6 py-2 sm:py-2.5 bg-gray-900/50 text-xs sm:text-sm font-medium text-white hover:text-purple-100 border border-gray-700/50 rounded-xl transition-all duration-300 group-hover:border-purple-500/50 group-hover:bg-gray-900/80 ${!isConnected || !message.trim() ? 'opacity-50 cursor-not-allowed' : ''}`}>
                            Send
                        </div>
                    </button>
                </div>
            </form>
        </div>
    );
}; 