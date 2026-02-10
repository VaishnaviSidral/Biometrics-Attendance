import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, Bell, Search, Sun, Moon, LogOut, User } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Header({ title, onMenuClick }) {
    const navigate = useNavigate();
    const location = useLocation();
    const { user, logout, isAdmin } = useAuth();
    const [searchTerm, setSearchTerm] = useState('');
    const [theme, setTheme] = useState(() => {
        // Get saved theme from localStorage or default to 'dark'
        return localStorage.getItem('theme') || 'dark';
    });

    // Hide header search on pages that have their own search or employee dashboard
    const hideSearch = location.pathname === '/employees' || location.pathname === '/employee-dashboard';

    useEffect(() => {
        // Apply theme to document
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleSearch = (e) => {
        if (e.key === 'Enter' && searchTerm.trim()) {
            // Navigate to All Employees page with search query
            navigate(`/employees?search=${encodeURIComponent(searchTerm.trim())}`);
        }
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <header className="header">
            <div className="flex items-center gap-4">
                <button
                    className="btn btn-ghost btn-icon"
                    onClick={onMenuClick}
                    style={{ display: 'none' }} // Hidden on desktop
                >
                    <Menu size={20} />
                </button>
                <h1 className="header-title">{title}</h1>
            </div>

            <div className="header-actions">
                {/* Search - hidden on All Employees page and employee dashboard */}
                {!hideSearch && isAdmin && (
                    <div style={{ position: 'relative' }}>
                        <Search
                            size={18}
                            style={{
                                position: 'absolute',
                                left: '12px',
                                top: '50%',
                                transform: 'translateY(-50%)',
                                color: 'var(--color-text-muted)',
                                pointerEvents: 'none'
                            }}
                        />
                        <input
                            type="text"
                            placeholder="Search employees..."
                            className="form-input"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            onKeyDown={handleSearch}
                            style={{
                                paddingLeft: '40px',
                                width: '240px',
                                background: 'var(--color-surface-elevated)'
                            }}
                        />
                    </div>
                )}

                {/* Theme Toggle */}
                <button
                    className="btn btn-ghost btn-icon"
                    onClick={toggleTheme}
                    title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                >
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>

                {/* User info and logout */}
                {user && (
                    <>
                        <div className="header-user-info">
                            <User size={18} />
                            <span>{user.username}</span>
                            <span className="user-role-badge">{user.role}</span>
                        </div>

                        <button
                            className="btn btn-ghost btn-icon"
                            onClick={handleLogout}
                            title="Logout"
                        >
                            <LogOut size={20} />
                        </button>
                    </>
                )}
            </div>
        </header>
    );
}
