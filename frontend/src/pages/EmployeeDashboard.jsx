import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Calendar, Clock, Building2, TrendingUp } from 'lucide-react';
import api from '../api/client';

export default function EmployeeDashboard() {
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [selectedWeek, setSelectedWeek] = useState('');
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchWeeklyCompliance();
    }, [selectedWeek]);

    const fetchWeeklyCompliance = async () => {
        try {
            setLoading(true);
            setError(null);
            const params = {};
            if (selectedWeek) params.week_start = selectedWeek;

            const response = await api.getEmployeeWeeklyCompliance(params);
            setData(response);

            // Set default week if not yet selected
            if (!selectedWeek && response.selected_week?.week_start) {
                setSelectedWeek(response.selected_week.week_start);
            }
        } catch (err) {
            console.error('Error fetching weekly compliance:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const getStatusColor = (status) => {
        const colors = {
            GREEN: { bg: '#dcfce7', text: '#16a34a', border: '#bbf7d0' },
            AMBER: { bg: '#fef9c3', text: '#ca8a04', border: '#fde68a' },
            RED: { bg: '#fecaca', text: '#dc2626', border: '#fca5a5' }
        };
        return colors[status] || colors.RED;
    };

    const getStatusLabel = (status) => {
        const labels = { GREEN: 'Compliance', AMBER: 'Mid-Compliance', RED: 'Non-Compliance' };
        return labels[status] || 'Non-Compliance';
    };

    if (loading && !data) {
        return (
            <div className="loading-overlay">
                <div className="loading-spinner"></div>
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="employee-dashboard">
                <div className="empty-state" style={{ padding: 'var(--spacing-8)' }}>
                    <h2 className="empty-state-title">Unable to load data</h2>
                    <p className="empty-state-text">{error}</p>
                    <button className="btn btn-primary" onClick={fetchWeeklyCompliance}>
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    const week = data?.selected_week || {};
    const dailyRecords = week.daily || [];
    const weeksSummary = data?.weeks_summary || [];
    const availableWeeks = data?.available_weeks || [];
    const statusColor = getStatusColor(week.status);

    return (
        <div className="employee-dashboard">
            {/* Header */}
            <div className="employee-dashboard-header">
                <div>
                    <h1 className="page-title">
                        Welcome, {data?.employee_name || user?.name || user?.email}
                    </h1>
                    <p className="page-subtitle">
                        Employee ID: {data?.employee_code || user?.employee_code || 'N/A'}
                        {data?.work_mode && <span> · {data.work_mode}</span>}
                    </p>
                </div>
            </div>

            {/* Week Filter */}
            <div className="employee-filter-section">
                <div className="employee-filters">
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label htmlFor="week" className="form-label">
                            <Calendar size={16} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                            Select Week:
                        </label>
                        <select
                            id="week"
                            className="form-input form-select"
                            value={selectedWeek}
                            onChange={(e) => setSelectedWeek(e.target.value)}
                            style={{ minWidth: '240px' }}
                        >
                            {/* Current week option (always present) */}
                            {!availableWeeks.find(w => w.week_start === selectedWeek) && selectedWeek && (
                                <option value={selectedWeek}>
                                    Current Week ({week.week_label || selectedWeek})
                                </option>
                            )}
                            {availableWeeks.map((w) => (
                                <option key={w.week_start} value={w.week_start}>
                                    {w.label}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Weekly Compliance Summary Cards */}
            {/* <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 'var(--spacing-4)',
                marginBottom: 'var(--spacing-6)'
            }}>
                <div className="card" style={{ padding: 'var(--spacing-4)', textAlign: 'center' }}>
                    <Clock size={24} style={{ margin: '0 auto var(--spacing-2)', color: '#3b82f6' }} />
                    <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'bold' }}>
                        {week.total_hours || '0h 00m'}
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>
                        Total Hours
                        {week.expected_hours && <span> / {week.expected_hours}</span>}
                    </div>
                </div>

                <div className="card" style={{ padding: 'var(--spacing-4)', textAlign: 'center' }}>
                    <Building2 size={24} style={{ margin: '0 auto var(--spacing-2)', color: '#8b5cf6' }} />
                    <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'bold' }}>
                        {week.wfo_days || 0} <span className="text-muted" style={{ fontSize: 'var(--font-size-base)', fontWeight: 400 }}>/ {week.required_days || 0}</span>
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>
                        WFO Days
                    </div>
                </div>

                <div className="card" style={{ padding: 'var(--spacing-4)', textAlign: 'center' }}>
                    <TrendingUp size={24} style={{ margin: '0 auto var(--spacing-2)', color: statusColor.text }} />
                    <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'bold', color: statusColor.text }}>
                        {week.compliance_percentage?.toFixed(1) || 0}%
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>
                        Compliance
                    </div>
                </div>

                <div className="card" style={{
                    padding: 'var(--spacing-4)',
                    textAlign: 'center',
                    background: statusColor.bg,
                    borderColor: statusColor.border
                }}>
                    <div style={{
                        fontSize: 'var(--font-size-xl)',
                        fontWeight: 'bold',
                        color: statusColor.text,
                        marginTop: 'var(--spacing-2)'
                    }}>
                        {getStatusLabel(week.status)}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: statusColor.text, marginTop: 'var(--spacing-1)' }}>
                        Week Status
                    </div>
                </div>
            </div> */}

            {/* Daily Breakdown Table */}
            <div className="employee-table-container" style={{ marginBottom: 'var(--spacing-6)' }}>
                <h3 style={{ padding: 'var(--spacing-4) var(--spacing-4) 0', fontWeight: 600 }}>
                    Daily Breakdown — {week.week_label || ''}
                </h3>
                <table className="employee-table">
                    <thead>
                        <tr>
                            <th>DATE</th>
                            <th>DAY</th>
                            <th>FIRST IN</th>
                            <th>LAST OUT</th>
                            <th>TOTAL HOURS</th>
                            <th>STATUS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {dailyRecords.length > 0 ? (
                            dailyRecords.map((record, index) => {
                                const isWeekend = !record.is_weekday;
                                return (
                                    <tr key={index} style={isWeekend ? { opacity: 0.5 } : {}}>
                                        <td>
                                            <div className="date-cell">
                                                <div className="date-primary">
                                                    {new Date(record.date).toLocaleDateString('en-US', {
                                                        month: 'short',
                                                        day: 'numeric',
                                                        year: 'numeric'
                                                    })}
                                                </div>
                                            </div>
                                        </td>
                                        <td>{record.day}</td>
                                        <td>{record.first_in || '-'}</td>
                                        <td>{record.last_out || '-'}</td>
                                        <td>
                                            <span style={{
                                                fontWeight: 600,
                                                color: record.total_minutes >= 540 ? '#16a34a'
                                                    : record.total_minutes >= 240 ? '#ca8a04'
                                                    : record.total_minutes > 0 ? '#dc2626'
                                                    : 'var(--color-text-muted)'
                                            }}>
                                                {record.total_hours}
                                            </span>
                                        </td>
                                        <td>
                                            {isWeekend ? (
                                                <span style={{
                                                    padding: '2px 8px', borderRadius: '999px',
                                                    fontSize: '12px', fontWeight: 600,
                                                    background: '#f1f5f9', color: '#64748b'
                                                }}>Weekend</span>
                                            ) : record.is_present ? (
                                                <span style={{
                                                    padding: '2px 8px', borderRadius: '999px',
                                                    fontSize: '12px', fontWeight: 600,
                                                    background: '#dcfce7', color: '#16a34a'
                                                }}>Present</span>
                                            ) : (
                                                <span style={{
                                                    padding: '2px 8px', borderRadius: '999px',
                                                    fontSize: '12px', fontWeight: 600,
                                                    background: '#fecaca', color: '#dc2626'
                                                }}>Absent</span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })
                        ) : (
                            <tr>
                                <td colSpan="6" className="empty-message">
                                    No attendance records found for this week.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Last 5 Weeks Summary */}
            {weeksSummary.length > 0 && (
                <div className="employee-table-container">
                    <h3 style={{ padding: 'var(--spacing-4) var(--spacing-4) 0', fontWeight: 600 }}>
                        Weekly Compliance Summary (Last 5 Weeks)
                    </h3>
                    <table className="employee-table">
                        <thead>
                            <tr>
                                <th>WEEK</th>
                                <th>TOTAL HOURS</th>
                                <th>WFO DAYS</th>
                                <th>COMPLIANCE</th>
                                <th>STATUS</th>
                            </tr>
                        </thead>
                        <tbody>
                            {weeksSummary.map((ws, index) => {
                                const wsColor = getStatusColor(ws.status);
                                return (
                                    <tr
                                        key={index}
                                        onClick={() => setSelectedWeek(ws.week_start)}
                                        style={{
                                            cursor: 'pointer',
                                            background: ws.week_start === selectedWeek ? 'var(--color-bg-subtle)' : undefined
                                        }}
                                    >
                                        <td style={{ fontWeight: ws.week_start === selectedWeek ? 600 : 400 }}>
                                            {ws.week_label}
                                        </td>
                                        <td>{ws.total_hours}</td>
                                        <td>
                                            {ws.wfo_days} <span className="text-muted">/ {ws.required_days}</span>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <div style={{
                                                    width: '60px', height: '6px',
                                                    borderRadius: '3px', background: '#e2e8f0'
                                                }}>
                                                    <div style={{
                                                        width: `${Math.min(ws.compliance_percentage, 100)}%`,
                                                        height: '100%', borderRadius: '3px',
                                                        background: wsColor.text
                                                    }} />
                                                </div>
                                                <span style={{ fontWeight: 600, fontSize: '13px' }}>
                                                    {ws.compliance_percentage.toFixed(1)}%
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            <span style={{
                                                padding: '4px 10px', borderRadius: '999px',
                                                fontSize: '12px', fontWeight: 600,
                                                background: wsColor.bg, color: wsColor.text
                                            }}>
                                                {getStatusLabel(ws.status)}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
