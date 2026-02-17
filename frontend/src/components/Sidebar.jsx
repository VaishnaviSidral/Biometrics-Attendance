import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    Upload,
    Users,
    CalendarDays,
    Settings,
    Fingerprint
} from 'lucide-react';

const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/upload', icon: Upload, label: 'Upload Data' },
    { path: '/employees', icon: Users, label: 'All Employees' },
    { path: '/monthly-report', icon: CalendarDays, label: 'Monthly Report' },
    { path: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
    return (
        <aside className="sidebar">
            {/* Logo */}
            <div className="sidebar-logo">
                <div className="sidebar-logo-icon">
                    <Fingerprint size={24} />
                </div>
                <span className="sidebar-logo-text">AttendanceHQ</span>
            </div>

            {/* Navigation */}
            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `nav-item ${isActive ? 'active' : ''}`
                        }
                    >
                        <item.icon className="nav-item-icon" size={20} />
                        <span>{item.label}</span>
                    </NavLink>
                ))}
            </nav>

            {/* Footer */}
            <div className="sidebar-footer" style={{
                marginTop: 'auto',
                padding: 'var(--spacing-4)',
                borderTop: '1px solid var(--color-border)',
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)'
            }}>
                <p>HR Admin Portal</p>
                <p>v1.0.0</p>
            </div>
        </aside>
    );
}
