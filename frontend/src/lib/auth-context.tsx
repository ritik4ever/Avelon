'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { auth } from '@/lib/api';

interface User {
    id: string;
    email: string;
    full_name: string | null;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, fullName?: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const stored = localStorage.getItem('avelon_token');
        const storedRefresh = localStorage.getItem('avelon_refresh_token');
        if (stored) {
            setToken(stored);
            auth.me(stored)
                .then(setUser)
                .catch(async () => {
                    // Try refresh
                    if (storedRefresh) {
                        try {
                            const result = await auth.refresh(storedRefresh);
                            localStorage.setItem('avelon_token', result.access_token);
                            localStorage.setItem('avelon_refresh_token', result.refresh_token);
                            setToken(result.access_token);
                            const me = await auth.me(result.access_token);
                            setUser(me);
                        } catch {
                            localStorage.removeItem('avelon_token');
                            localStorage.removeItem('avelon_refresh_token');
                            setToken(null);
                        }
                    } else {
                        localStorage.removeItem('avelon_token');
                        setToken(null);
                    }
                })
                .finally(() => setLoading(false));
        } else {
            setLoading(false);
        }
    }, []);

    const login = async (email: string, password: string) => {
        const result = await auth.login(email, password);
        localStorage.setItem('avelon_token', result.access_token);
        localStorage.setItem('avelon_refresh_token', result.refresh_token);
        setToken(result.access_token);
        const me = await auth.me(result.access_token);
        setUser(me);
    };

    const register = async (email: string, password: string, fullName?: string) => {
        await auth.register(email, password, fullName);
        await login(email, password);
    };

    const logout = () => {
        localStorage.removeItem('avelon_token');
        localStorage.removeItem('avelon_refresh_token');
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) throw new Error('useAuth must be used within AuthProvider');
    return context;
}
