import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth.tsx';
import { FiMessageSquare, FiUsers, FiCode, FiGithub, FiBook, FiBox } from 'react-icons/fi';
import { API_BASE_URL } from '@/config/env.ts';

export default function HomePage() {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    navigate('/login');
    return null;
  }

  const features = [
    {
      title: 'Human-Agent Chat',
      description: 'Engage in real-time conversations with AI agents. Test different models and explore various capabilities in a seamless chat interface.',
      icon: FiMessageSquare,
      path: '/chat',
      gradient: 'from-blue-500/10 via-blue-400/5 to-cyan-500/10',
      hoverGradient: 'hover:from-blue-500/20 hover:via-blue-400/15 hover:to-cyan-500/20',
      iconColor: 'text-blue-400',
      hoverText: 'group-hover:text-blue-300',
      shadow: 'hover:shadow-blue-500/10'
    },
    {
      title: 'Agent Collaboration',
      description: 'Observe autonomous interactions between AI agents. Configure their personalities and analyze their collaborative problem-solving capabilities.',
      icon: FiUsers,
      path: '/collaboration',
      gradient: 'from-purple-500/10 via-pink-400/5 to-pink-500/10',
      hoverGradient: 'hover:from-purple-500/20 hover:via-pink-400/15 hover:to-pink-500/20',
      iconColor: 'text-purple-400',
      hoverText: 'group-hover:text-purple-300',
      shadow: 'hover:shadow-purple-500/10'
    }
  ];

  const keyFeatures = [
    { icon: FiBox, title: 'Autonomous Agents', description: 'Independent communication with async processing loops' },
    { icon: FiMessageSquare, title: 'Real-time Communication', description: 'WebSocket-based updates for seamless interactions' },
    { icon: FiUsers, title: 'Multi-Provider Support', description: 'OpenAI, Anthropic, Groq, and Google AI integration' },
    { icon: FiCode, title: 'Extensible Design', description: 'Modular architecture with automatic session management' }
  ];

  return (
    <div className="space-y-8 sm:space-y-12">
      {/* Welcome Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-gray-800/50 via-gray-800/30 to-gray-800/50 border border-gray-700/50 backdrop-blur-xl">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 animate-gradient-slow"></div>
        <div className="relative p-6 sm:p-8 md:p-10">
          <div className="max-w-4xl mx-auto text-center">
            <div className="flex flex-col items-center gap-4">
              <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20">
                <span className="text-xs font-medium text-blue-400">Welcome back</span>
                <span className="text-xs font-medium text-gray-400">{user?.user}</span>
              </div>
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-transparent bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-500 bg-clip-text leading-tight animate-text">
                AgentConnect Platform
              </h1>
              <p className="text-gray-300 text-base sm:text-lg md:text-xl">
                Experience the future of AI collaboration. Engage with intelligent agents and explore the possibilities of autonomous interactions.
              </p>
              <div className="flex flex-wrap justify-center gap-4 mt-4">
                <a
                  href="https://github.com/AKKI0511/AgentConnect"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-300 bg-gray-800/50 rounded-lg border border-gray-700/50 hover:bg-gray-700/50 transition-all duration-300"
                >
                  <FiGithub className="w-4 h-4" />
                  Star on GitHub
                </a>
                <a
                  href={`${API_BASE_URL}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-400 bg-blue-500/10 rounded-lg border border-blue-500/20 hover:bg-blue-500/20 transition-all duration-300"
                >
                  <FiBook className="w-4 h-4" />
                  API Documentation
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Features Section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {keyFeatures.map((feature, index) => (
          <div
            key={index}
            className="relative overflow-hidden rounded-xl bg-gray-800/50 border border-gray-700/50 p-4 backdrop-blur-sm hover:bg-gray-800/70 transition-all duration-300"
          >
            <div className="flex items-start gap-3">
              <feature.icon className="w-5 h-5 text-blue-400 mt-1" />
              <div>
                <h3 className="text-sm font-semibold text-white mb-1">{feature.title}</h3>
                <p className="text-xs text-gray-400">{feature.description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Features Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {features.map((feature) => (
          <div
            key={feature.path}
            onClick={() => navigate(feature.path)}
            className={`group relative overflow-hidden rounded-2xl bg-gradient-to-br ${feature.gradient} p-1 transition-all duration-500 ${feature.hoverGradient} cursor-pointer shadow-lg ${feature.shadow}`}
          >
            <div className="relative z-10 h-full p-6 bg-gray-800/95 rounded-xl border border-gray-700/50 transition-all duration-500 group-hover:-translate-y-1 group-hover:bg-gray-800/90">
              <div className="flex flex-col h-full">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex-1">
                    <h2 className={`text-xl sm:text-2xl font-semibold text-white mb-3 transition-colors duration-300 ${feature.hoverText}`}>
                      {feature.title}
                    </h2>
                    <p className="text-gray-300 text-sm sm:text-base leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                  <feature.icon className={`w-6 h-6 sm:w-8 sm:h-8 ${feature.iconColor} flex-shrink-0 group-hover:scale-110 transition-transform duration-300`} />
                </div>
                <div className={`flex items-center ${feature.iconColor} font-medium mt-auto`}>
                  <span className="text-sm sm:text-base">Get Started</span>
                  <svg
                    className="w-4 h-4 sm:w-5 sm:h-5 ml-2 transform transition-transform duration-500 group-hover:translate-x-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Resources Section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <a
          href={`${API_BASE_URL}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-gray-700/10 via-gray-600/5 to-gray-700/10 p-1 transition-all duration-500 hover:from-gray-700/20 hover:via-gray-600/15 hover:to-gray-700/20 cursor-pointer shadow-lg hover:shadow-gray-500/10"
        >
          <div className="relative z-10 h-full p-6 bg-gray-800/95 rounded-xl border border-gray-700/50 transition-all duration-500 group-hover:-translate-y-1 group-hover:bg-gray-800/90">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-gray-300">Swagger Documentation</h3>
                <p className="text-gray-400 text-sm">Interactive API documentation with Swagger UI</p>
              </div>
              <FiBook className="w-6 h-6 text-gray-400 group-hover:scale-110 transition-transform duration-300" />
            </div>
          </div>
        </a>

        <a
          href={`${API_BASE_URL}/redoc`}
          target="_blank"
          rel="noopener noreferrer"
          className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-gray-700/10 via-gray-600/5 to-gray-700/10 p-1 transition-all duration-500 hover:from-gray-700/20 hover:via-gray-600/15 hover:to-gray-700/20 cursor-pointer shadow-lg hover:shadow-gray-500/10"
        >
          <div className="relative z-10 h-full p-6 bg-gray-800/95 rounded-xl border border-gray-700/50 transition-all duration-500 group-hover:-translate-y-1 group-hover:bg-gray-800/90">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-gray-300">ReDoc Documentation</h3>
                <p className="text-gray-400 text-sm">Alternative API documentation with ReDoc</p>
              </div>
              <FiCode className="w-6 h-6 text-gray-400 group-hover:scale-110 transition-transform duration-300" />
            </div>
          </div>
        </a>
      </div>
    </div>
  );
} 