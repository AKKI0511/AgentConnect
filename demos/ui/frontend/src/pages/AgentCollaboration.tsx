import React, { useEffect, useState } from 'react';
// import { useLocation, useNavigate } from 'react-router-dom';
import { ChatWindow } from '../components/ChatWindow';
import { AgentStatus } from '../components/AgentStatus';
import { apiService } from '../services/api';
import { AgentStatus as AgentStatusType, AgentConfigRequest, CreateSessionRequest } from '../types/chat';
import { useWebSocket } from '../hooks/useWebSocket';
import { FiSettings, FiZap, FiMessageSquare, FiCode, FiUsers, FiActivity, FiCpu } from 'react-icons/fi';
import { Provider } from '../types/chat';

// Available capabilities as per API documentation
const AVAILABLE_CAPABILITIES = [
    { id: 'conversation', label: 'Conversation', icon: FiMessageSquare },
    { id: 'analysis', label: 'Analysis', icon: FiCode }
];

interface AgentConfig {
    personality: string;
    role: string;
    capabilities: string[];
    provider: string;
    model: string;
}

interface ConfigurationPanelProps {
    providers: Record<string, Provider>;
    agent1Config: AgentConfig;
    setAgent1Config: React.Dispatch<React.SetStateAction<AgentConfig>>;
    agent2Config: AgentConfig;
    setAgent2Config: React.Dispatch<React.SetStateAction<AgentConfig>>;
    isConnecting: boolean;
    createSession: () => void;
}

const ConfigurationPanel = ({
    providers,
    agent1Config,
    setAgent1Config,
    agent2Config,
    setAgent2Config,
    isConnecting,
    createSession
}: ConfigurationPanelProps) => (
    <div className="max-w-4xl mx-auto relative px-3 sm:px-0">
        {/* Background Effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 via-pink-400/20 to-purple-500/20 transform rotate-12 blur-3xl opacity-20 animate-pulse"></div>
        
        {/* Main Content */}
        <div className="relative bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl p-6 sm:p-8 space-y-8">
            <div className="flex items-center gap-3 mb-6">
                <FiUsers className="w-6 h-6 text-purple-400" />
                <h2 className="text-xl font-semibold text-white">Configure Agent Collaboration</h2>
            </div>

            <div className="space-y-8">
                {/* Agent 1 Configuration */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2">
                        <FiCpu className="w-5 h-5 text-purple-400" />
                        <h3 className="text-lg font-semibold text-white">Agent 1 Configuration</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Provider Selection */}
                        <div className="group space-y-2">
                            <label className="block text-sm font-medium text-gray-300 ml-1">
                                AI Provider
                            </label>
                            <select
                                value={agent1Config.provider}
                                onChange={(e) => {
                                    const provider = e.target.value;
                                    setAgent1Config(prev => ({
                                        ...prev,
                                        provider,
                                        model: providers[provider]?.models?.[0] || ''
                                    }));
                                }}
                                className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                            >
                                <option value="">Select a provider</option>
                                {Object.entries(providers)
                                    .filter(([_, provider]) => provider.models?.length > 0)
                                    .map(([key, provider]) => (
                                        <option key={key} value={key} className="bg-gray-800">
                                            {provider.name || key}
                                        </option>
                                    ))
                                }
                            </select>
                        </div>

                        {/* Model Selection */}
                        {agent1Config.provider && providers[agent1Config.provider]?.models && (
                            <div className="group space-y-2">
                                <label className="block text-sm font-medium text-gray-300 ml-1">
                                    AI Model
                                </label>
                                <select
                                    value={agent1Config.model}
                                    onChange={(e) => setAgent1Config(prev => ({ ...prev, model: e.target.value }))}
                                    className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                                >
                                    {providers[agent1Config.provider].models.map((model: string) => (
                                        <option key={model} value={model} className="bg-gray-800">
                                            {model}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        <div className="group space-y-2">
                            <label className="block text-sm font-medium text-gray-300 ml-1">
                                Role
                            </label>
                            <input
                                type="text"
                                value={agent1Config.role}
                                onChange={(e) => setAgent1Config(prev => ({ ...prev, role: e.target.value }))}
                                placeholder="e.g., Problem Solver, Analyst, Creative Thinker"
                                className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                            />
                        </div>
                        <div className="group space-y-2">
                            <label className="block text-sm font-medium text-gray-300 ml-1">
                                Personality
                            </label>
                            <input
                                type="text"
                                value={agent1Config.personality}
                                onChange={(e) => setAgent1Config(prev => ({ ...prev, personality: e.target.value }))}
                                placeholder="e.g., Analytical, Precise, Detail-oriented"
                                className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                            />
                        </div>
                    </div>
                    {/* Capabilities Selection */}
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-300 ml-1">
                            Capabilities
                        </label>
                        <div className="grid grid-cols-2 gap-4">
                            {AVAILABLE_CAPABILITIES.map((cap) => (
                                <label
                                    key={cap.id}
                                    className="flex items-center space-x-2 p-3 rounded-lg bg-gray-900/30 border border-gray-700/50 cursor-pointer hover:bg-gray-900/50 transition-all duration-300"
                                >
                                    <input
                                        type="checkbox"
                                        checked={agent1Config.capabilities.includes(cap.id)}
                                        onChange={(e) => {
                                            if (e.target.checked) {
                                                setAgent1Config(prev => ({
                                                    ...prev,
                                                    capabilities: [...prev.capabilities, cap.id]
                                                }));
                                            } else {
                                                setAgent1Config(prev => ({
                                                    ...prev,
                                                    capabilities: prev.capabilities.filter(c => c !== cap.id)
                                                }));
                                            }
                                        }}
                                        className="form-checkbox h-4 w-4 text-purple-500 rounded border-gray-700 bg-gray-900/50 focus:ring-purple-500/50"
                                    />
                                    <div className="flex items-center gap-2">
                                        <cap.icon className="w-4 h-4 text-gray-400" />
                                        <span className="text-sm text-gray-300">{cap.label}</span>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Agent 2 Configuration */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2">
                        <FiCpu className="w-5 h-5 text-purple-400" />
                        <h3 className="text-lg font-semibold text-white">Agent 2 Configuration</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Provider Selection */}
                        <div className="group space-y-2">
                            <label className="block text-sm font-medium text-gray-300 ml-1">
                                AI Provider
                            </label>
                            <select
                                value={agent2Config.provider}
                                onChange={(e) => {
                                    const provider = e.target.value;
                                    setAgent2Config(prev => ({
                                        ...prev,
                                        provider,
                                        model: providers[provider]?.models?.[0] || ''
                                    }));
                                }}
                                className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                            >
                                <option value="">Select a provider</option>
                                {Object.entries(providers)
                                    .filter(([_, provider]) => provider.models?.length > 0)
                                    .map(([key, provider]) => (
                                        <option key={key} value={key} className="bg-gray-800">
                                            {provider.name || key}
                                        </option>
                                    ))
                                }
                            </select>
                        </div>

                        {/* Model Selection */}
                        {agent2Config.provider && providers[agent2Config.provider]?.models && (
                            <div className="group space-y-2">
                                <label className="block text-sm font-medium text-gray-300 ml-1">
                                    AI Model
                                </label>
                                <select
                                    value={agent2Config.model}
                                    onChange={(e) => setAgent2Config(prev => ({ ...prev, model: e.target.value }))}
                                    className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                                >
                                    {providers[agent2Config.provider].models.map((model: string) => (
                                        <option key={model} value={model} className="bg-gray-800">
                                            {model}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        <div className="group space-y-2">
                            <label className="block text-sm font-medium text-gray-300 ml-1">
                                Role
                            </label>
                            <input
                                type="text"
                                value={agent2Config.role}
                                onChange={(e) => setAgent2Config(prev => ({ ...prev, role: e.target.value }))}
                                placeholder="e.g., Critic, Evaluator, Supporter"
                                className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                            />
                        </div>
                        <div className="group space-y-2">
                            <label className="block text-sm font-medium text-gray-300 ml-1">
                                Personality
                            </label>
                            <input
                                type="text"
                                value={agent2Config.personality}
                                onChange={(e) => setAgent2Config(prev => ({ ...prev, personality: e.target.value }))}
                                placeholder="e.g., Creative, Supportive, Open-minded"
                                className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 transition-all duration-300"
                            />
                        </div>
                    </div>
                    {/* Capabilities Selection */}
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-300 ml-1">
                            Capabilities
                        </label>
                        <div className="grid grid-cols-2 gap-4">
                            {AVAILABLE_CAPABILITIES.map((cap) => (
                                <label
                                    key={cap.id}
                                    className="flex items-center space-x-2 p-3 rounded-lg bg-gray-900/30 border border-gray-700/50 cursor-pointer hover:bg-gray-900/50 transition-all duration-300"
                                >
                                    <input
                                        type="checkbox"
                                        checked={agent2Config.capabilities.includes(cap.id)}
                                        onChange={(e) => {
                                            if (e.target.checked) {
                                                setAgent2Config(prev => ({
                                                    ...prev,
                                                    capabilities: [...prev.capabilities, cap.id]
                                                }));
                                            } else {
                                                setAgent2Config(prev => ({
                                                    ...prev,
                                                    capabilities: prev.capabilities.filter(c => c !== cap.id)
                                                }));
                                            }
                                        }}
                                        className="form-checkbox h-4 w-4 text-purple-500 rounded border-gray-700 bg-gray-900/50 focus:ring-purple-500/50"
                                    />
                                    <div className="flex items-center gap-2">
                                        <cap.icon className="w-4 h-4 text-gray-400" />
                                        <span className="text-sm text-gray-300">{cap.label}</span>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Start Button */}
                <button
                    onClick={createSession}
                    disabled={isConnecting || 
                        !agent1Config.provider || !agent1Config.model || agent1Config.capabilities.length === 0 ||
                        !agent2Config.provider || !agent2Config.model || agent2Config.capabilities.length === 0}
                    className="relative w-full group overflow-hidden rounded-lg"
                >
                    <div className="absolute inset-0 w-3/6 bg-gradient-to-r from-purple-500/50 via-pink-400/50 to-purple-500/50 blur-lg group-hover:w-full transition-all duration-1000"></div>
                    <div className="relative w-full px-4 py-3 bg-gray-900/50 text-sm font-medium text-white hover:text-purple-100 border border-gray-700 rounded-lg transition-all duration-300 group-hover:border-purple-500/50 group-hover:bg-gray-900/80 disabled:opacity-50 disabled:cursor-not-allowed">
                        {isConnecting ? (
                            <div className="flex items-center justify-center gap-2">
                                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span>Creating Session...</span>
                            </div>
                        ) : (
                            <div className="flex items-center justify-center gap-2">
                                <FiZap className="w-4 h-4" />
                                <span>Start Agent Collaboration</span>
                            </div>
                        )}
                    </div>
                </button>
            </div>
        </div>
    </div>
);

export const AgentCollaboration: React.FC = () => {
    // const location = useLocation();
    // const navigate = useNavigate();
    const [providers, setProviders] = useState<Record<string, Provider>>({});
    const [agent1Config, setAgent1Config] = useState<AgentConfig>({
        personality: 'analytical and precise',
        role: 'Problem Solver',
        capabilities: ['conversation', 'analysis'],
        provider: '',
        model: ''
    });
    const [agent2Config, setAgent2Config] = useState<AgentConfig>({
        personality: 'creative and supportive',
        role: 'Creative Assistant',
        capabilities: ['conversation', 'analysis'],
        provider: '',
        model: ''
    });
    const [agent1Status, setAgent1Status] = useState<AgentStatusType | null>(null);
    const [agent2Status, setAgent2Status] = useState<AgentStatusType | null>(null);

    const {
        session,
        error,
        isConnecting,
        connect,
        sendMessage,
        disconnect
    } = useWebSocket({ sessionType: 'agent_agent' });

    // Simple cleanup when component unmounts
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    // Initial data fetching
    useEffect(() => {
        const fetchProviders = async () => {
            try {
                const providersData = await apiService.getProviders();
                setProviders(providersData);
                
                // Filter providers that have models
                const availableProviders = Object.entries(providersData)
                    .filter(([_, provider]) => provider.models?.length > 0);
                
                if (availableProviders.length > 0) {
                    const [firstProviderId, firstProvider] = availableProviders[0];
                    setAgent1Config(prev => ({
                        ...prev,
                        provider: firstProviderId,
                        model: firstProvider.models[0] || ''
                    }));
                    setAgent2Config(prev => ({
                        ...prev,
                        provider: firstProviderId,
                        model: firstProvider.models[0] || ''
                    }));
                }
            } catch (err) {
                console.error('Failed to fetch providers:', err);
            }
        };

        fetchProviders();
    }, []);

    const createSession = async () => {
        try {
            const agent1: AgentConfigRequest = {
                provider: agent1Config.provider,
                model: agent1Config.model,
                capabilities: agent1Config.capabilities,
                personality: `${agent1Config.role}: ${agent1Config.personality}`,
                metadata: {
                    role: agent1Config.role
                }
            };

            const agent2: AgentConfigRequest = {
                provider: agent2Config.provider,
                model: agent2Config.model,
                capabilities: agent2Config.capabilities,
                personality: `${agent2Config.role}: ${agent2Config.personality}`,
                metadata: {
                    role: agent2Config.role
                }
            };

            const sessionConfig: CreateSessionRequest = {
                session_type: 'agent_agent',
                agents: {
                    agent1,
                    agent2
                },
                interaction_modes: ['agent_to_agent'],
                metadata: {
                    purpose: 'collaborative analysis',
                    agent1_role: agent1Config.role,
                    agent2_role: agent2Config.role
                }
            };

            const newSession = await apiService.createSession(sessionConfig);
            await connect({
                ...newSession,
                messages: []
            });

            // Fetch initial agent statuses
            const agent1Id = newSession.agents.agent1?.agent_id;
            const agent2Id = newSession.agents.agent2?.agent_id;
            
            if (agent1Id && agent2Id) {
                const [agent1Data, agent2Data] = await Promise.all([
                    apiService.getAgentStatus(agent1Id),
                    apiService.getAgentStatus(agent2Id)
                ]);
                setAgent1Status(agent1Data);
                setAgent2Status(agent2Data);
            }
        } catch (err) {
            console.error('Failed to create session:', err);
        }
    };

    const handleNewSession = async () => {
        try {
            // First disconnect to prevent reconnection attempts
            disconnect();
            
            // Then delete the session if it exists
            if (session?.session_id) {
                await apiService.deleteSession(session.session_id);
            }
            
            // Reset states
            setAgent1Status(null);
            setAgent2Status(null);
            
            // Fetch providers again
            const providersData = await apiService.getProviders();
            setProviders(providersData);
            
            const availableProviders = Object.entries(providersData)
                .filter(([_, provider]) => provider.models?.length > 0);
            
            if (availableProviders.length > 0) {
                const [firstProviderId, firstProvider] = availableProviders[0];
                setAgent1Config(prev => ({
                    ...prev,
                    provider: firstProviderId,
                    model: firstProvider.models[0] || ''
                }));
                setAgent2Config(prev => ({
                    ...prev,
                    provider: firstProviderId,
                    model: firstProvider.models[0] || ''
                }));
            }
        } catch (err) {
            console.error('Failed to start new session:', err);
        }
    };

    return (
        <div className="container mx-auto px-4 py-6">
            {!session ? (
                <ConfigurationPanel
                    providers={providers}
                    agent1Config={agent1Config}
                    setAgent1Config={setAgent1Config}
                    agent2Config={agent2Config}
                    setAgent2Config={setAgent2Config}
                    isConnecting={isConnecting}
                    createSession={createSession}
                />
            ) : (
                <div className="h-full grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
                    <div className="flex flex-col h-full">
                        <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl p-4 mb-4">
                            <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-0 sm:justify-between">
                                <div className="flex items-center gap-3">
                                    <FiUsers className="w-5 h-5 text-purple-400" />
                                    <h2 className="text-lg font-semibold text-white">Agent Collaboration</h2>
                                </div>
                                <button
                                    onClick={handleNewSession}
                                    className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-gray-300 bg-gray-800/50 rounded-lg border border-gray-700/50 hover:bg-gray-700/50 transition-all duration-300"
                                >
                                    <FiSettings className="w-4 h-4" />
                                    <span>New Session</span>
                                </button>
                            </div>
                        </div>
                        <div className="flex-1 min-h-0 bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl overflow-hidden">
                            <ChatWindow
                                session={session}
                                onSendMessage={sendMessage}
                                showHeader={false}
                                className="h-full"
                            />
                        </div>
                        {error && (
                            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/50 text-red-400 rounded-2xl backdrop-blur-xl">
                                Error: {error}
                            </div>
                        )}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                        {agent1Status && (
                            <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl p-4">
                                <div className="flex items-center gap-2 mb-3">
                                    <FiActivity className="w-4 h-4 text-purple-400" />
                                    <h3 className="text-sm font-medium text-white">
                                        {agent1Config.role} Status
                                    </h3>
                                </div>
                                <AgentStatus status={agent1Status} />
                            </div>
                        )}
                        {agent2Status && (
                            <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl p-4">
                                <div className="flex items-center gap-2 mb-3">
                                    <FiActivity className="w-4 h-4 text-purple-400" />
                                    <h3 className="text-sm font-medium text-white">
                                        {agent2Config.role} Status
                                    </h3>
                                </div>
                                <AgentStatus status={agent2Status} />
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AgentCollaboration; 