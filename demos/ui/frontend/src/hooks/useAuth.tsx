import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { authService } from '../services/auth';

// Extend TokenClaims for our User type
interface User {
  user: string;  // User ID from token claims
  type: string;
  exp: number;
  iat: number;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

// Create context with undefined as initial value
const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initAuth = async () => {
      try {
        if (authService.isAuthenticated()) {
          const token = authService.getAccessToken();
          if (token) {
            const claims = await authService.verifyToken(token);
            setUser({
              user: claims.user,
              type: claims.type,
              exp: claims.exp,
              iat: claims.iat
            });
          }
        }
      } catch (err) {
        console.error('Auth initialization error:', err);
        authService.logout();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      await authService.login(username, password);
      
      // After successful login, get user info from token
      const token = authService.getAccessToken();
      if (token) {
        const claims = await authService.verifyToken(token);
        setUser({
          user: claims.user,
          type: claims.type,
          exp: claims.exp,
          iat: claims.iat
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    try {
      setLoading(true);
      authService.logout();
      setUser(null);
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const value: AuthContextType = {
    isAuthenticated: !!user,
    user,
    login,
    logout,
    loading,
    error
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 