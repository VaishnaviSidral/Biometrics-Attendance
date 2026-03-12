import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Calendar, Clock, Building2, TrendingUp } from 'lucide-react';
import api from '../api/client';
import {
    getCurrentISOWeek,
    generateISOWeeks,
    isoWeekToDateString,
    getPreviousISOWeeks,
    parseISOWeek,
    getYearRange,
    getWeeksInMonth,
    getMonthNames,
} from '../utils/isoWeek';

export default function EmployeeDashboard() {
    const { user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    // Calendar-based year + month + week
    const currentISO = getCurrentISOWeek();
    const [selectedYear, setSelectedYear] = useState(currentISO.year);
    const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
    const [selectedWeekValue, setSelectedWeekValue] = useState(
        `${currentISO.year}-W${String(currentISO.week).padStart(2, '0')}`
    );

    const years = useMemo(() => getYearRange(), []);
    const months = useMemo(() => getMonthNames(), []);
    const isoWeeks = useMemo(() => getWeeksInMonth(selectedYear, selectedMonth), [selectedYear, selectedMonth]);

    // Last 5 weeks (calendar-calculated, cross-year safe)
    const last5Weeks = useMemo(() => getPreviousISOWeeks(selectedWeekValue, 5), [selectedWeekValue]);

    // State for last-5-week API results
    const [weeksSummaryData, setWeeksSummaryData] = useState({});

    const weekStartDate = useMemo(
        () => isoWeekToDateString(selectedWeekValue),
        [selectedWeekValue]
    );

    // Fetch selected week's data when week changes
    useEffect(() => {
        if (weekStartDate) {
            fetchWeeklyCompliance(weekStartDate);
        }
    }, [weekStartDate]);

    // Fetch last 5 weeks data when selection changes
    useEffect(() => {
        if (last5Weeks.length > 0) {
            fetchLast5Weeks();
        }
    }, [last5Weeks.join(',')]);

    const fetchWeeklyCompliance = async (dateStr) => {
        try {
            setLoading(true);
            setError(null);
            const response = await api.getEmployeeWeeklyCompliance({ week_start: dateStr });
            setData(response);
        } catch (err) {
            console.error('Error fetching weekly compliance:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchLast5Weeks = async () => {
        const results = {};
        for (const wk of last5Weeks) {
            const dateStr = isoWeekToDateString(wk);
            if (!dateStr) continue;
            try {
                const resp = await api.getEmployeeWeeklyCompliance({ week_start: dateStr });
                results[wk] = resp?.selected_week || null;
            } catch {
                results[wk] = null;
            }
        }
        setWeeksSummaryData(results);
    };

    const handleYearChange = (newYear) => {
        setSelectedYear(newYear);
        if (newYear === currentISO.year) {
            setSelectedMonth(new Date().getMonth() + 1);
            setSelectedWeekValue(
                `${currentISO.year}-W${String(currentISO.week).padStart(2, '0')}`
            );
        } else {
            setSelectedMonth(1);
            const weeksInJan = getWeeksInMonth(newYear, 1);
            setSelectedWeekValue(weeksInJan[0]?.value || `${newYear}-W01`);
        }
    };

    const handleMonthChange = (newMonth) => {
        setSelectedMonth(newMonth);
        const weeksInMonth = getWeeksInMonth(selectedYear, newMonth);
        if (weeksInMonth.length > 0) {
            setSelectedWeekValue(weeksInMonth[0].value);
        }
    };

    const getStatusColor = (status) => {
        const colors = {
            'Compliance':      { bg: '#dcfce7', text: '#16a34a', border: '#bbf7d0' },
            'Mid-Compliance':  { bg: '#fef9c3', text: '#ca8a04', border: '#fde68a' },
            'Non-Compliance':  { bg: '#fecaca', text: '#dc2626', border: '#fca5a5' },
            'Leave':           { bg: 'rgba(107, 114, 128, 0.125)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.3)' },
            'Weekend':         { bg: 'rgba(107, 114, 128, 0.125)', text: '#6b7280', border: 'rgba(107, 114, 128, 0.3)' }
        };
        return colors[status] || colors['Non-Compliance'];
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
                    <button className="btn btn-primary" onClick={() => fetchWeeklyCompliance(weekStartDate)}>
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    const week = data?.selected_week || {};
    const dailyRecords = week.daily || [];
    const statusColor = getStatusColor(week.status);
    const selectedWeekObj = isoWeeks.find(w => w.value === selectedWeekValue);

    // Build last 5 weeks rows (calendar-driven, with API data if available)
    const last5WeeksRows = last5Weeks.map((wk) => {
        const wkObj = (() => {
            const p = parseISOWeek(wk);
            if (!p) return null;
            const allWeeks = generateISOWeeks(p.year);
            return allWeeks.find(w => w.value === wk);
        })();

        const apiData = weeksSummaryData[wk];

        return {
            weekValue: wk,
            weekLabel: wkObj?.label || wk,
            weekStart: wkObj?.weekStart || isoWeekToDateString(wk),
            totalHours: apiData?.total_hours || '0h 00m',
            totalMinutes: apiData?.total_minutes || 0,
            wfoDays: apiData?.wfo_days || 0,
            requiredDays: apiData?.required_days || 0,
            compliancePercentage: apiData?.compliance_percentage ?? 0,
            status: apiData?.status || 'Non-Compliance',
        };
    });

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

            {/* Year + Month + Week Filter */}
            <div className="employee-filter-section">
                <div className="employee-filters" style={{ display: 'flex', alignItems: 'flex-end', gap: 'var(--spacing-3)' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">
                            <Calendar size={16} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                            Year
                        </label>
                        <select
                            className="form-input form-select"
                            value={selectedYear}
                            onChange={(e) => handleYearChange(Number(e.target.value))}
                            style={{ minWidth: '100px' }}
                        >
                            {years.map((y) => (
                                <option key={y} value={y}>{y}</option>
                            ))}
                        </select>
                    </div>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Month</label>
                        <select
                            className="form-input form-select"
                            value={selectedMonth}
                            onChange={(e) => handleMonthChange(Number(e.target.value))}
                            style={{ minWidth: '140px' }}
                        >
                            {months.map((m, i) => (
                                <option key={i + 1} value={i + 1}>{m}</option>
                            ))}
                        </select>
                    </div>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Week</label>
                        <select
                            className="form-input form-select"
                            value={selectedWeekValue}
                            onChange={(e) => setSelectedWeekValue(e.target.value)}
                            style={{ minWidth: '300px' }}
                        >
                            {isoWeeks.map((w) => (
                                <option key={w.value} value={w.value}>
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
                        {week.wfo_days || 0}{' '}
                        <span className="text-muted" style={{ fontSize: 'var(--font-size-base)', fontWeight: 400 }}>
                            / {week.required_days || 0}
                        </span>
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
                        {week.status}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-sm)', color: statusColor.text, marginTop: 'var(--spacing-1)' }}>
                        Week Status
                    </div>
                </div>
            </div> */}

            {/* Daily Breakdown Table */}
            <div className="employee-table-container" style={{ marginBottom: 'var(--spacing-6)' }}>
                <h3 style={{ padding: 'var(--spacing-4) var(--spacing-4) 0', fontWeight: 600 }}>
                    Daily Breakdown — {selectedWeekObj?.label || selectedWeekValue}
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
                                            {(() => {
                                                const status = !record.is_weekday
                                                    ? 'Weekend'
                                                    : (record.compliance_status === 'LEAVE' ? 'Leave' : record.compliance_status);

                                                const color = getStatusColor(status);

                                                return (
                                                    <span
                                                        style={{
                                                            padding: '4px 10px',
                                                            borderRadius: '999px',
                                                            fontSize: '12px',
                                                            fontWeight: 600,
                                                            background: color.bg,
                                                            color: color.text
                                                        }}
                                                    >
                                                        {status}
                                                    </span>
                                                );
                                            })()}
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

            {/* Last 5 Weeks Summary (calendar-calculated) */}
            <div className="employee-table-container">
                <h3 style={{ padding: 'var(--spacing-4) var(--spacing-4) 0', fontWeight: 600 }}>
                    Weekly Compliance Summary (Previous 5 Weeks)
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
                        {last5WeeksRows.map((ws, index) => {
                            const wsColor = getStatusColor(ws.status);
                            return (
                                <tr
                                    key={index}
                                    // onClick={() => {
                                    //     const p = parseISOWeek(ws.weekValue);
                                    //     if (p) {
                                    //         setSelectedYear(p.year);
                                    //         setSelectedWeekValue(ws.weekValue);
                                    //     }
                                    // }}
                                    style={{ cursor: 'pointer' }}
                                >
                                    <td style={{ fontWeight: 400 }}>
                                        {ws.weekLabel}
                                    </td>
                                    <td>{ws.totalHours}</td>
                                    <td>
                                        {ws.wfoDays}{' '}
                                        <span className="text-muted">/ {ws.requiredDays}</span>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <div style={{
                                                width: '60px', height: '6px',
                                                borderRadius: '3px', background: '#e2e8f0'
                                            }}>
                                                <div style={{
                                                    width: `${Math.min(ws.compliancePercentage, 100)}%`,
                                                    height: '100%', borderRadius: '3px',
                                                    background: wsColor.text
                                                }} />
                                            </div>
                                            <span style={{ fontWeight: 600, fontSize: '13px' }}>
                                                {ws.compliancePercentage.toFixed(1)}%
                                            </span>
                                        </div>
                                    </td>
                                    <td>
                                        <span style={{
                                            padding: '4px 10px', borderRadius: '999px',
                                            fontSize: '12px', fontWeight: 600,
                                            background: wsColor.bg, color: wsColor.text
                                        }}>
                                            {ws.status}
                                        </span>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
