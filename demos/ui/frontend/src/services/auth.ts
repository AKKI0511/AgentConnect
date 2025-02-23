import { config } from '@/config/env';
import { AuthError } from '@/utils/errors';

interface AuthResponse {
    access_token: string;
    token_type: string;
    expires_in: number;
}

interface TokenClaims {
    user: string;
    exp: number;
    iat: number;
    type: string;
}

class AuthService {
    private getStoredToken(): string | null {
        return localStorage.getItem(config.auth.tokenKey);
    }

    private setStoredToken(token: string): void {
        localStorage.setItem(config.auth.tokenKey, token);
    }

    private removeStoredToken(): void {
        localStorage.removeItem(config.auth.tokenKey);
    }

    getAccessToken(): string | null {
        return this.getStoredToken();
    }

    isAuthenticated(): boolean {
        const token = this.getStoredToken();
        if (!token) return false;

        try {
            const claims = this.parseToken(token);
            return claims.exp * 1000 > Date.now();
        } catch {
            return false;
        }
    }

    async login(username: string, password: string): Promise<void> {
        try {
            const response = await fetch(`${config.api.baseUrl}${config.auth.loginEndpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
            });

            if (!response.ok) {
                throw new AuthError('Invalid credentials');
            }

            const data: AuthResponse = await response.json();
            this.setStoredToken(data.access_token);
        } catch (error) {
            if (error instanceof AuthError) throw error;
            throw new AuthError('Login failed');
        }
    }

    async verifyToken(token: string = this.getStoredToken() || ''): Promise<TokenClaims> {
        try {
            const response = await fetch(`${config.api.baseUrl}${config.auth.verifyEndpoint}`, {
                method: 'POST',
                headers: {
                    'Authorization': `${config.auth.tokenType} ${token}`,
                },
            });

            if (!response.ok) {
                throw new AuthError('Invalid token');
            }

            const data: TokenClaims = await response.json();
            return data;
        } catch (error) {
            if (error instanceof AuthError) throw error;
            throw new AuthError('Token verification failed');
        }
    }

    private parseToken(token: string): TokenClaims {
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(
                atob(base64)
                    .split('')
                    .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                    .join('')
            );
            return JSON.parse(jsonPayload);
        } catch {
            throw new AuthError('Invalid token format');
        }
    }

    logout(): void {
        this.removeStoredToken();
    }
}

export const authService = new AuthService(); 