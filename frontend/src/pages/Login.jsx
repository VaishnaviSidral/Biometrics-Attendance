import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';

function LoginForm() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [googleClientId, setGoogleClientId] = useState('');
    const [googleEnabled, setGoogleEnabled] = useState(false);
    const { login, googleLogin } = useAuth();
    const navigate = useNavigate();
    const googleButtonRef = useRef(null);

    useEffect(() => {
        // Fetch auth config to get Google Client ID
        fetchAuthConfig();
    }, []);

    const handleRedirect = useCallback((user) => {
        if (user.role === 'ADMIN') {
            navigate('/');
        } else if (user.role === 'EMPLOYEE') {
            navigate('/employee-dashboard');
        }
    }, [navigate]);

    const handleGoogleSuccess = useCallback(async (credentialResponse) => {
        setError('');
        setLoading(true);

        try {
            const user = await googleLogin(credentialResponse.credential);
            handleRedirect(user);
        } catch (err) {
            setError(err.message || 'Google login failed.');
        } finally {
            setLoading(false);
        }
    }, [googleLogin, handleRedirect]);

    // Initialize Google Sign-In when client ID is available
    useEffect(() => {
        if (!googleEnabled || !googleClientId || !googleButtonRef.current) return;

        const initializeGoogleSignIn = () => {
            if (typeof window.google === 'undefined' || !window.google.accounts) {
                // GIS script not loaded yet, retry after a short delay
                setTimeout(initializeGoogleSignIn, 100);
                return;
            }

            window.google.accounts.id.initialize({
                client_id: googleClientId,
                callback: handleGoogleSuccess,
            });

            window.google.accounts.id.renderButton(googleButtonRef.current, {
                theme: 'filled_blue',
                size: 'large',
                text: 'signin_with',
                shape: 'rectangular',
                width: googleButtonRef.current.offsetWidth || 300,
            });
        };

        initializeGoogleSignIn();
    }, [googleEnabled, googleClientId, handleGoogleSuccess]);

    const fetchAuthConfig = async () => {
        try {
            const config = await api.getAuthConfig();
            console.log("AUTH CONFIG:", config);
            if (config.google_client_id) {
                setGoogleClientId(config.google_client_id);
                setGoogleEnabled(config.google_enabled);
            }
        } catch (err) {
            console.log('Auth config not available:', err.message);
        }
    };

    const handleEmailLogin = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const user = await login(email, password);
            handleRedirect(user);
        } catch (err) {
            setError(err.message || 'Login failed. Please check your email.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-header">
                    <div className="login-icon">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="40"
                            height="40"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                    </div>
                    <h1 className="login-title">OfficeTrack</h1>
                    <p className="login-subtitle">Biometric Attendance System</p>
                </div>

                {error && (
                    <div className="login-error" style={{ margin: '0 0 16px 0' }}>
                        {error}
                    </div>
                )}

                {/* Email Login Form */}
                <form onSubmit={handleEmailLogin} className="login-form">
                    <div className="form-group">
                        <label htmlFor="email" className="form-label">
                            Email
                        </label>
                        <input
                            id="email"
                            type="email"
                            className="form-input"
                            placeholder="Enter your organization email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="password" className="form-label">
                            Password
                        </label>
                        <input
                            id="password"
                            type="password"
                            className="form-input"
                            placeholder="Enter any password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>

                    <button
                        type="submit"
                        className="btn btn-primary btn-block"
                        disabled={loading}
                    >
                        {loading ? 'Signing in...' : 'Sign In'}
                    </button>

                    <div style={{ marginBottom: '20px' }}>

                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            margin: '20px 0',
                            gap: '12px'
                        }}>
                            <div style={{ flex: 1, height: '1px', background: 'var(--color-border)' }} />
                            <span className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>
                                or sign in with email
                            </span>
                            <div style={{ flex: 1, height: '1px', background: 'var(--color-border)' }} />
                        </div>
                    </div>
                </form>
                {/* Google Sign-In */}
                {googleEnabled && (
                    <div style={{ marginBottom: '20px' }}>
                        <div ref={googleButtonRef} style={{ width: '100%' }} />
                    </div>
                )}
            </div>
        </div>
    );
}

export default function Login() {
    return <LoginForm />;
}
