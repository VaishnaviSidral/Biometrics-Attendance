import { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Check for stored token and user on mount
        const storedToken = localStorage.getItem('auth_token');
        const storedUser = localStorage.getItem('auth_user');

        if (storedToken && storedUser) {
            try {
                const parsedUser = JSON.parse(storedUser);
                if (parsedUser && typeof parsedUser === 'object') {
                    setToken(storedToken);
                    setUser(parsedUser);
                    api.setAuthToken(storedToken);
                } else {
                    localStorage.removeItem('auth_token');
                    localStorage.removeItem('auth_user');
                }
            } catch (error) {
                console.error('Error parsing stored user data:', error);
                localStorage.removeItem('auth_token');
                localStorage.removeItem('auth_user');
            }
        }

        setLoading(false);
    }, []);

    // Email login (password can be anything - per README)
    const login = async (email, password) => {
        try {
            const response = await api.login(email, password);

            const { access_token, user: userData } = response;

            localStorage.setItem('auth_token', access_token);
            localStorage.setItem('auth_user', JSON.stringify(userData));

            setToken(access_token);
            setUser(userData);
            api.setAuthToken(access_token);

            return userData;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    };

    // Google OAuth login
    const googleLogin = async (credential) => {
        try {
            const response = await api.googleLogin(credential);

            const { access_token, user: userData } = response;

            localStorage.setItem('auth_token', access_token);
            localStorage.setItem('auth_user', JSON.stringify(userData));

            setToken(access_token);
            setUser(userData);
            api.setAuthToken(access_token);

            return userData;
        } catch (error) {
            console.error('Google login error:', error);
            throw error;
        }
    };

    const logout = () => {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');

        setToken(null);
        setUser(null);
        api.setAuthToken(null);
    };

    const value = {
        user,
        token,
        login,
        googleLogin,
        logout,
        loading,
        isAuthenticated: !!token,
        isAdmin: user?.role === 'ADMIN',
        isEmployee: user?.role === 'EMPLOYEE'
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
