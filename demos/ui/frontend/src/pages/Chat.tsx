import React, { useEffect, useState } from 'react';
import { ChatWindow } from '../components/ChatWindow';
import { apiService, type CreateSessionRequest } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { FiCpu, FiSettings, FiZap, FiMessageSquare, FiCode } from 'react-icons/fi';

interface ProviderModel {
    name: string;
    models: string[];
    capabilities: string[];
    default_model: string;
    is_available: boolean;
}

// Available capabilities as per API documentation
const AVAILABLE_CAPABILITIES = [
    { id: 'conversation', label: 'Conversation', icon: FiMessageSquare },
    { id: 'analysis', label: 'Analysis', icon: FiCode }
];

interface ConfigurationPanelProps {
    providers: Record<string, ProviderModel>;
    selectedProvider: string;
    setSelectedProvider: (provider: string) => void;
    selectedModel: string;
    setSelectedModel: (model: string) => void;
    capabilities: string[];
    setCapabilities: React.Dispatch<React.SetStateAction<string[]>>;
    personality: string;
    setPersonality: (personality: string) => void;
    isConnecting: boolean;
    createSession: () => void;
}

const ConfigurationPanel = ({
    providers,
    selectedProvider,
    setSelectedProvider,
    selectedModel,
    setSelectedModel,
    capabilities,
    setCapabilities,
    personality,
    setPersonality,
    isConnecting,
    createSession
}: ConfigurationPanelProps) => (
    <div className="max-w-2xl mx-auto relative px-3 sm:px-0">
        {/* Background Effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 via-cyan-400/20 to-blue-500/20 transform rotate-12 blur-3xl opacity-20 animate-pulse"></div>
        
        {/* Main Content */}
        <div className="relative bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl p-6 sm:p-8 space-y-6">
            <div className="flex items-center gap-3 mb-6">
                <FiCpu className="w-6 h-6 text-blue-400" />
                <h2 className="text-xl font-semibold text-white">Configure AI Assistant</h2>
            </div>

            <div className="space-y-6">
                {/* Provider Selection */}
                <div className="group space-y-2">
                    <label className="block text-sm font-medium text-gray-300 ml-1">
                        AI Provider
                    </label>
                    <select
                        value={selectedProvider}
                        onChange={(e) => {
                            const provider = e.target.value;
                            setSelectedProvider(provider);
                            if (providers[provider]?.models?.length > 0) {
                                setSelectedModel(providers[provider].default_model);
                            }
                        }}
                        className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all duration-300"
                    >
                        <option value="">Select a provider</option>
                        {Object.entries(providers)
                            .filter(([_, provider]) => provider.is_available)
                            .map(([key, provider]) => (
                                <option key={key} value={key} className="bg-gray-800">
                                    {provider.name || key}
                                </option>
                            ))
                        }
                    </select>
                    {selectedProvider && (
                        <p className="text-xs text-gray-400 mt-1 ml-1">
                            Available models: {providers[selectedProvider]?.models?.length || 0}
                        </p>
                    )}
                </div>

                {/* Model Selection */}
                {selectedProvider && providers[selectedProvider]?.models && (
                    <div className="group space-y-2">
                        <label className="block text-sm font-medium text-gray-300 ml-1">
                            AI Model
                        </label>
                        <select
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            className="w-full h-12 px-4 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all duration-300"
                        >
                            {providers[selectedProvider].models.map((model: string) => (
                                <option key={model} value={model} className="bg-gray-800">
                                    {model}
                                </option>
                            ))}
                        </select>
                    </div>
                )}

                {/* Capabilities Selection */}
                <div className="group space-y-2">
                    <label className="block text-sm font-medium text-gray-300 ml-1">
                        Capabilities
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                        {AVAILABLE_CAPABILITIES.map((cap) => (
                            <label
                                key={cap.id}
                                className="flex items-center space-x-2 p-3 rounded-lg bg-gray-900/30 border border-gray-700/50 cursor-pointer hover:bg-gray-900/50 transition-all duration-300"
                            >
                                <input
                                    type="checkbox"
                                    checked={capabilities.includes(cap.id)}
                                    onChange={(e) => {
                                        if (e.target.checked) {
                                            setCapabilities((prev: string[]) => [...prev, cap.id]);
                                        } else {
                                            setCapabilities((prev: string[]) => prev.filter((c: string) => c !== cap.id));
                                        }
                                    }}
                                    className="form-checkbox h-4 w-4 text-blue-500 rounded border-gray-700 bg-gray-900/50 focus:ring-blue-500/50"
                                />
                                <div className="flex items-center gap-2">
                                    <cap.icon className="w-4 h-4 text-gray-400" />
                                    <span className="text-sm text-gray-300">{cap.label}</span>
                                </div>
                            </label>
                        ))}
                    </div>
                </div>

                {/* Personality Input */}
                <div className="group space-y-2">
                    <label className="block text-sm font-medium text-gray-300 ml-1">
                        AI Personality
                    </label>
                    <textarea
                        value={personality}
                        onChange={(e) => setPersonality(e.target.value)}
                        placeholder="Describe how you want the AI to behave (e.g., professional, friendly, analytical)..."
                        rows={3}
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all duration-300 resize-none"
                    />
                    <p className="text-xs text-gray-400 mt-1 ml-1">
                        Describe the AI's personality and behavior style
                    </p>
                </div>

                {/* Start Button */}
                <button
                    onClick={createSession}
                    disabled={isConnecting || !selectedProvider || !selectedModel || capabilities.length === 0}
                    className="relative w-full group overflow-hidden rounded-lg"
                >
                    <div className="absolute inset-0 w-3/6 bg-gradient-to-r from-blue-500/50 via-cyan-400/50 to-blue-500/50 blur-lg group-hover:w-full transition-all duration-1000"></div>
                    <div className="relative w-full px-4 py-3 bg-gray-900/50 text-sm font-medium text-white hover:text-blue-100 border border-gray-700 rounded-lg transition-all duration-300 group-hover:border-blue-500/50 group-hover:bg-gray-900/80 disabled:opacity-50 disabled:cursor-not-allowed">
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
                                <span>Start Chat Session</span>
                            </div>
                        )}
                    </div>
                </button>
            </div>
        </div>
    </div>
);

export default function Chat() {
    const [providers, setProviders] = useState<Record<string, ProviderModel>>({});
    const [selectedProvider, setSelectedProvider] = useState<string>('');
    const [selectedModel, setSelectedModel] = useState<string>('');
    const [capabilities, setCapabilities] = useState<string[]>(['conversation']);
    const [personality, setPersonality] = useState<string>('helpful and professional');
    const [isConfiguring, setIsConfiguring] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const {
        session,
        isConnecting,
        connect,
        sendMessage,
        disconnect
    } = useWebSocket({ sessionType: 'human_agent' });

    useEffect(() => {
        const fetchProviders = async () => {
            try {
                const providersData = await apiService.getProviders();
                
                // The providers are directly in the response, not under a 'providers' property
                if (!providersData) {
                    console.error('No provider data received');
                    return;
                }

                // Format the providers data
                const formattedProviders: Record<string, ProviderModel> = {};
                
                try {
                    Object.entries(providersData).forEach(([key, value]: [string, any]) => {
                        if (value) {
                            formattedProviders[key] = {
                                name: value.name || key,
                                models: Array.isArray(value.models) ? value.models : [],
                                capabilities: [], // Capabilities are not provider-specific
                                default_model: value.models?.[0] || '', // Use first model as default
                                is_available: true // All returned providers are available
                            };
                        }
                    });
                } catch (err) {
                    console.error('Error formatting provider data:', err);
                    return;
                }
                
                setProviders(formattedProviders);
                
                // Select first available provider
                const availableProviders = Object.entries(formattedProviders)
                    .filter(([_, provider]) => provider.is_available);
                
                if (availableProviders.length > 0) {
                    const [firstProviderId, firstProvider] = availableProviders[0];
                    setSelectedProvider(firstProviderId);
                    setSelectedModel(firstProvider.default_model);
                }
            } catch (err) {
                console.error('Failed to fetch providers:', err);
            }
        };

        fetchProviders();
    }, []);

    // Handle cleanup effect when component unmounts or route changes
    useEffect(() => {
        // Cleanup function that runs only on unmount
        const cleanup = () => {
            console.log('Unmounting Chat component');
            disconnect();
        };

        // Handle beforeunload event
        window.addEventListener('beforeunload', cleanup);
        
        return () => {
            window.removeEventListener('beforeunload', cleanup);
            cleanup();
        };
    }, [disconnect]); // Add disconnect to dependencies

    const handleConfigureClick = () => {
        disconnect();
        setIsConfiguring(true);
    };

    const handleCreateSession = async () => {
        try {
            const config: CreateSessionRequest = {
                session_type: 'human_agent',
                agents: {
                    ai_agent: {
                        provider: selectedProvider,
                        model: selectedModel,
                        capabilities,
                        personality
                    }
                },
                interaction_modes: ['human_to_agent'],
                metadata: {
                    purpose: 'human-ai chat'
                }
            };

            const newSession = await apiService.createSession(config);
            await connect({
                ...newSession,
                messages: []
            });
            setIsConfiguring(false);
        } catch (err) {
            console.error('Failed to create session:', err);
            setError(err instanceof Error ? err.message : 'Failed to create session');
        }
    };

    const ChatInterface = () => (
        <div className="h-full grid grid-cols-1 gap-4">
            <div className="flex flex-col h-full">
                <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl p-4 mb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <FiCpu className="w-5 h-5 text-blue-400" />
                            <h2 className="text-lg font-semibold text-white">AI Assistant</h2>
                        </div>
                        <button
                            onClick={handleConfigureClick}
                            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-gray-300 bg-gray-800/50 rounded-lg border border-gray-700/50 hover:bg-gray-700/50 transition-all duration-300"
                        >
                            <FiSettings className="w-4 h-4" />
                            <span>Configure</span>
                        </button>
                    </div>
                </div>
                <div className="flex-1 min-h-0 bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl overflow-hidden">
                    {session && (
                        <ChatWindow
                            session={session}
                            onSendMessage={sendMessage}
                            showHeader={false}
                            className="h-full"
                        />
                    )}
                </div>
                {error && (
                    <div className="mt-4 p-4 bg-red-500/10 border border-red-500/50 text-red-400 rounded-2xl backdrop-blur-xl">
                        Error: {error}
                    </div>
                )}
            </div>
        </div>
    );

    return (
        <div className="container mx-auto px-4 py-6">
            {isConfiguring ? (
                <ConfigurationPanel
                    providers={providers}
                    selectedProvider={selectedProvider}
                    setSelectedProvider={setSelectedProvider}
                    selectedModel={selectedModel}
                    setSelectedModel={setSelectedModel}
                    capabilities={capabilities}
                    setCapabilities={setCapabilities}
                    personality={personality}
                    setPersonality={setPersonality}
                    isConnecting={isConnecting}
                    createSession={handleCreateSession}
                />
            ) : <ChatInterface />}
        </div>
    );
} 