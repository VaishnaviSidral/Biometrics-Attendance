import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, Search, Sun, Moon, LogOut, User, ChevronDown } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Header({ title, onMenuClick }) {
    const navigate = useNavigate();
    const location = useLocation();
    const { user, logout, isAdmin, isEmployee } = useAuth();
    const [searchTerm, setSearchTerm] = useState('');
    const [theme, setTheme] = useState(() => {
        return localStorage.getItem('theme') || 'dark';
    });
    const [showRoleDropdown, setShowRoleDropdown] = useState(false);
    const dropdownRef = useRef(null);

    // Hide header search on pages that have their own search or employee dashboard
    const hideSearch = location.pathname === '/employees' || location.pathname === '/employee-dashboard';

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === 'dark' ? 'light' : 'dark');
    };

    const handleSearch = (e) => {
        if (e.key === 'Enter' && searchTerm.trim()) {
            navigate(`/employees?search=${encodeURIComponent(searchTerm.trim())}`);
        }
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const handleRoleSwitch = (role) => {
        setShowRoleDropdown(false);
        
        // Navigate based on role selection
        if (role === 'admin' && isAdmin) {
            navigate('/'); // Admin dashboard
        } else {
            navigate('/employee-dashboard'); // Employee dashboard
        }
    };

    // Determine current display role
    const currentRole = isAdmin && !location.pathname.startsWith('/employee') ? 'admin' : 'employee';
    
    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setShowRoleDropdown(false);
            }
        };
        
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Display name: use name if available, fallback to email
    const displayName = user?.name || user?.email || 'User';

    return (
        <header className="header">
            <div className="flex items-center gap-4">
                <button
                    className="btn btn-ghost btn-icon"
                    onClick={onMenuClick}
                    style={{ display: 'none' }}
                >
                    <Menu size={20} />
                </button>
                <h1 className="header-title">{title}</h1>
            </div>

            <div className="header-actions">
                {/* Search */}
                {/* {!hideSearch && isAdmin && (
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
                )} */}

                {/* Theme Toggle */}
                <button
                    className="btn btn-ghost btn-icon"
                    onClick={toggleTheme}
                    title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                >
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>

                {/* User info and role dropdown */}
                {user && (
                    <>
                        <div className="header-user-info">
                            <User size={18} />
                            <span>{displayName}</span>
                            
                            {/* Role Dropdown */}
                            <div className="role-dropdown-container" ref={dropdownRef}>
                                <button
                                    className="role-dropdown-trigger"
                                    onClick={() => setShowRoleDropdown(!showRoleDropdown)}
                                    title="Switch role view"
                                >
                                    <span className="current-role">{currentRole === 'admin' ? 'Admin' : 'Employee'}</span>
                                    <ChevronDown size={16} className={`dropdown-arrow ${showRoleDropdown ? 'open' : ''}`} />
                                </button>
                                
                                {showRoleDropdown && (
                                    <div className="role-dropdown-menu">
                                        <button
                                            className={`role-option ${currentRole === 'employee' ? 'active' : ''}`}
                                            onClick={() => handleRoleSwitch('employee')}
                                        >
                                            <User size={16} />
                                            <span>Employee</span>
                                        </button>
                                        
                                        {isAdmin && (
                                            <button
                                                className={`role-option ${currentRole === 'admin' ? 'active' : ''}`}
                                                onClick={() => handleRoleSwitch('admin')}
                                            >
                                                <User size={16} />
                                                <span>Admin</span>
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
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
