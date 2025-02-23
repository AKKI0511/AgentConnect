import React from 'react';
import { AgentStatus as AgentStatusType } from '../types/chat';

interface AgentStatusProps {
    status: AgentStatusType;
    className?: string;
}

export const AgentStatus: React.FC<AgentStatusProps> = ({ status, className = '' }) => {
    const getStatusColor = (status: 'active' | 'inactive' | 'cooldown') => {
        switch (status) {
            case 'active':
                return {
                    dot: 'bg-green-500',
                    text: 'text-green-300',
                    border: 'border-green-500/20',
                    background: 'bg-green-500/10'
                };
            case 'inactive':
                return {
                    dot: 'bg-gray-500',
                    text: 'text-gray-300',
                    border: 'border-gray-500/20',
                    background: 'bg-gray-500/10'
                };
            case 'cooldown':
                return {
                    dot: 'bg-yellow-500',
                    text: 'text-yellow-300',
                    border: 'border-yellow-500/20',
                    background: 'bg-yellow-500/10'
                };
            default:
                return {
                    dot: 'bg-gray-500',
                    text: 'text-gray-300',
                    border: 'border-gray-500/20',
                    background: 'bg-gray-500/10'
                };
        }
    };

    const statusStyle = getStatusColor(status.status);

    return (
        <div className={`group transition-all duration-300 ${className}`}>
            <div className="flex items-center justify-between mb-3 sm:mb-4">
                <h3 className="text-base sm:text-lg font-semibold text-transparent bg-gradient-to-r from-purple-400 via-pink-300 to-purple-500 bg-clip-text">
                    {status.name || status.agent_id}
                </h3>
                <div className={`flex items-center px-1.5 sm:px-2 py-0.5 sm:py-1 rounded-full ${statusStyle.background} ${statusStyle.border} transition-all duration-300`}>
                    <div className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${statusStyle.dot} mr-1.5 sm:mr-2`} />
                    <span className={`text-[10px] sm:text-xs font-medium capitalize ${statusStyle.text}`}>{status.status}</span>
                </div>
            </div>
            
            <div className="space-y-1.5 sm:space-y-2 text-xs sm:text-sm">
                <div className="flex justify-between items-center p-1.5 sm:p-2 rounded-lg bg-gray-900/30 backdrop-blur-sm border border-gray-700/30">
                    <span className="text-gray-400">Type</span>
                    <span className="text-gray-200 font-medium">{status.agent_type}</span>
                </div>
                <div className="flex justify-between items-center p-1.5 sm:p-2 rounded-lg bg-gray-900/30 backdrop-blur-sm border border-gray-700/30">
                    <span className="text-gray-400">Messages</span>
                    <span className="text-gray-200 font-medium">{status.message_count}</span>
                </div>
                <div className="flex justify-between items-center p-1.5 sm:p-2 rounded-lg bg-gray-900/30 backdrop-blur-sm border border-gray-700/30">
                    <span className="text-gray-400">Active Conversations</span>
                    <span className="text-gray-200 font-medium">{status.metadata.active_conversations || 0}</span>
                </div>
                {status.metadata.cooldown_until && (
                    <div className="flex justify-between items-center p-1.5 sm:p-2 rounded-lg bg-gray-900/30 backdrop-blur-sm border border-gray-700/30">
                        <span className="text-gray-400">Cooldown Until</span>
                        <span className="text-gray-200 font-medium">
                            {new Date(status.metadata.cooldown_until).toLocaleTimeString()}
                        </span>
                    </div>
                )}
            </div>

            <div className="mt-3 sm:mt-4">
                <h4 className="text-xs sm:text-sm font-medium text-gray-400 mb-1.5 sm:mb-2 ml-0.5 sm:ml-1">Capabilities</h4>
                <div className="flex flex-wrap gap-1.5 sm:gap-2">
                    {status.capabilities.map((capability) => (
                        <span
                            key={capability}
                            className="px-2 sm:px-3 py-0.5 sm:py-1 text-[10px] sm:text-xs rounded-full bg-purple-500/10 text-purple-200 border border-purple-500/20 transition-all duration-300 hover:bg-purple-500/20"
                        >
                            {capability}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}; 