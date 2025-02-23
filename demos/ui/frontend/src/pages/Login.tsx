import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth.tsx';
import { FiLock, FiUser } from 'react-icons/fi';

export default function Login() {
    const navigate = useNavigate();
    const { login, error, loading } = useAuth();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await login(username, password);
            navigate('/');
        } catch (err) {
            // Error is handled by useAuth
            console.error('Login failed:', err);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 animate-gradient-slow flex items-center justify-center px-4">
            <div className="w-full max-w-md relative">
                {/* Background Effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 via-cyan-400/20 to-blue-500/20 transform rotate-12 blur-3xl opacity-20 animate-pulse"></div>
                
                {/* Main Content */}
                <div className="relative bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl shadow-xl hover:shadow-blue-500/10 transition-all duration-300">
                    <div className="p-6 sm:p-8">
                        {/* Header */}
                        <div className="text-center space-y-3 mb-8">
                            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20">
                                <span className="text-xs font-medium text-blue-400">Welcome back</span>
                            </div>
                            <h1 className="text-3xl sm:text-4xl font-bold text-transparent bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-500 bg-clip-text animate-text">
                                Welcome to AgentConnect
                            </h1>
                            <p className="text-gray-400 text-sm sm:text-base">
                                Sign in to start collaborating with AI agents
                            </p>
                        </div>

                        {/* Form */}
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div className="space-y-4">
                                <div className="relative group">
                                    <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">
                                        Username
                                    </label>
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            <FiUser className="h-5 w-5 text-gray-400" />
                                        </div>
                                        <input
                                            id="username"
                                            name="username"
                                            type="text"
                                            autoComplete="username"
                                            required
                                            value={username}
                                            onChange={(e) => setUsername(e.target.value)}
                                            className="w-full pl-10 pr-4 py-3 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all duration-300"
                                            placeholder="Enter your username"
                                        />
                                    </div>
                                </div>

                                <div className="relative group">
                                    <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                                        Password
                                    </label>
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            <FiLock className="h-5 w-5 text-gray-400" />
                                        </div>
                                        <input
                                            id="password"
                                            name="password"
                                            type="password"
                                            autoComplete="current-password"
                                            required
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            className="w-full pl-10 pr-4 py-3 bg-gray-900/50 border border-gray-700 text-gray-100 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all duration-300"
                                            placeholder="Enter your password"
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="relative group overflow-hidden rounded-lg">
                                <div className="absolute inset-0 w-3/6 bg-gradient-to-r from-blue-500/50 via-cyan-400/50 to-blue-500/50 blur-lg group-hover:w-full transition-all duration-1000"></div>
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="relative w-full py-3 bg-gray-900/50 text-white font-medium rounded-lg transition-all duration-300 group-hover:bg-gray-900/80 group-hover:border-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {loading ? (
                                        <div className="flex items-center justify-center gap-2">
                                            <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                            <span>Signing in...</span>
                                        </div>
                                    ) : (
                                        <span>Sign in</span>
                                    )}
                                </button>
                            </div>
                        </form>

                        {/* Error Message */}
                        {error && (
                            <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg backdrop-blur-xl">
                                <p className="text-red-400 text-sm text-center">{error}</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
} 