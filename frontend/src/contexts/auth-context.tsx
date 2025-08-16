'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { User } from '@/types/api';
import { apiClient } from '@/lib/api-client';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!user && apiClient.isAuthenticated();

  const login = async (username: string, password: string) => {
    try {
      const response = await apiClient.login(username, password);
      if (response.data) {
        // Support both user and user_info fields from backend
        const responseData = response.data as any;
        const userData = responseData.user || responseData.user_info;
        if (userData) {
          setUser(userData);
        }
      }
    } catch (error) {
      setUser(null);
      throw error;
    }
  };

  const logout = () => {
    apiClient.logout();
    setUser(null);
  };

  const checkAuth = async () => {
    setIsLoading(true);
    try {
      if (apiClient.isAuthenticated()) {
        // Check if we have a cached user
        const cachedUser = apiClient.getCurrentUser();
        if (cachedUser) {
          setUser(cachedUser);
        } else {
          // Try to get current user from API
          const response = await apiClient.get<User>('/auth/me');
          if (response.data) {
            setUser(response.data);
            // Cache the user
            if (typeof window !== 'undefined') {
              localStorage.setItem('user', JSON.stringify(response.data));
            }
          }
        }
      }
    } catch (error) {
      // If token is invalid, clear everything
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated,
        login,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}