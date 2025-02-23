import React from 'react';
import { ChatMessage as ChatMessageType } from '../types/chat';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import 'github-markdown-css/github-markdown-dark.css';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import { useEffect } from 'react';

interface ChatMessageProps {
    message: ChatMessageType;
    isOwnMessage: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, isOwnMessage }) => {
    useEffect(() => {
        // Highlight code blocks after component mounts or updates
        document.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block as HTMLElement);
        });
    }, [message.content]);

    const getMessageStyle = () => {
        const baseStyle = 'backdrop-blur-sm transition-all duration-300 shadow-lg ';
        
        switch (message.type) {
            case 'error':
                return baseStyle + 'bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 text-red-100 shadow-red-500/10';
            case 'info':
                return baseStyle + 'bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/20 text-blue-100 shadow-blue-500/10';
            case 'system':
                return baseStyle + 'bg-gray-500/10 border border-gray-500/20 hover:bg-gray-500/20 text-gray-200 shadow-gray-500/10';
            case 'response':
                return baseStyle + 'bg-green-500/10 border border-green-500/20 hover:bg-green-500/20 text-green-100 shadow-green-500/10';
            case 'stop':
                return baseStyle + 'bg-yellow-500/10 border border-yellow-500/20 hover:bg-yellow-500/20 text-yellow-100 shadow-yellow-500/10';
            case 'cooldown':
                return baseStyle + 'bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 text-purple-100 shadow-purple-500/10';
            default:
                return baseStyle + (isOwnMessage
                    ? 'bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 text-gray-100 shadow-purple-500/10'
                    : 'bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/20 text-gray-100 shadow-blue-500/10');
        }
    };

    return (
        <div className={`group flex ${isOwnMessage ? 'justify-end' : 'justify-start'} mb-3 sm:mb-4 last:mb-0`}>
            <div className={`max-w-[95%] sm:max-w-[85%] rounded-2xl px-3 py-2 sm:px-4 sm:py-3 ${getMessageStyle()}`}>
                {(
                    <div className="text-[10px] sm:text-xs font-medium mb-1 sm:mb-2 opacity-90 flex items-center gap-1.5 sm:gap-2">
                        <span className="px-1.5 sm:px-2 py-0.5 rounded-full bg-gray-800/50 border border-gray-600/50">
                            {message.type.toUpperCase()}
                        </span>
                    </div>
                )}
                <div className="markdown-body bg-transparent !text-current text-left text-sm sm:text-base">
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkMath]}
                        rehypePlugins={[rehypeKatex]}
                    >
                        {message.content}
                    </ReactMarkdown>
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2 mt-1.5 sm:mt-2 text-[10px] sm:text-xs opacity-75">
                    <span>{new Date(message.timestamp).toLocaleTimeString(undefined, {
                        hour: '2-digit',
                        minute: '2-digit'
                    })}</span>
                    {message.sender && (
                        <>
                            <span className="w-0.5 sm:w-1 h-0.5 sm:h-1 rounded-full bg-current opacity-50" />
                            <span>{message.sender}</span>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}; 