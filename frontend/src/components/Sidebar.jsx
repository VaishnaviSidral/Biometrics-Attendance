import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    Upload,
    Users,
    CalendarDays,
    Settings,
    Fingerprint,
    ChevronDown,
    ChevronRight,
    Building2,
    Shuffle
} from 'lucide-react';

const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/upload', icon: Upload, label: 'Upload Data' },
    { path: '/employees', icon: Users, label: 'All Employees' },
    { path: '/settings', icon: Settings, label: 'Settings' },
];

const monthlyReportSubItems = [
    { path: '/monthly-report/wfo', icon: Building2, label: 'WFO' },
    { path: '/monthly-report/hybrid', icon: Shuffle, label: 'Hybrid' },
];

export default function Sidebar() {
    const location = useLocation();
    const isMonthlyReportActive = location.pathname.startsWith('/monthly-report');
    const [monthlyReportOpen, setMonthlyReportOpen] = useState(isMonthlyReportActive);

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
                {/* Regular nav items before Monthly Report */}
                {navItems.slice(0, 3).map((item) => (
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

                {/* Monthly Report with submenu */}
                <div
                    className="nav-group"
                    onMouseEnter={() => setMonthlyReportOpen(true)}
                    onMouseLeave={() => setMonthlyReportOpen(false)}
                >
                    <div
                        className={`nav-item nav-item-toggle ${isMonthlyReportActive ? 'active' : ''}`}
                    >
                        <CalendarDays className="nav-item-icon" size={20} />
                        <span>Monthly Report</span>
                        {monthlyReportOpen ? (
                            <ChevronDown size={16} className="nav-chevron" />
                        ) : (
                            <ChevronRight size={16} className="nav-chevron" />
                        )}
                    </div>

                    {monthlyReportOpen && (
                        <div className="nav-submenu">
                            {monthlyReportSubItems.map((item) => (
                                <NavLink
                                    key={item.path}
                                    to={item.path}
                                    className={({ isActive }) =>
                                        `nav-item nav-submenu-item ${isActive ? 'active' : ''}`
                                    }
                                >
                                    <item.icon className="nav-item-icon" size={16} />
                                    <span>{item.label}</span>
                                </NavLink>
                            ))}
                        </div>
                    )}
                </div>

                {/* Remaining nav items (Settings) */}
                {navItems.slice(3).map((item) => (
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
