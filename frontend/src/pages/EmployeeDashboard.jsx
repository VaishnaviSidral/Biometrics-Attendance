import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { LogOut } from 'lucide-react';
import api from '../api/client';

export default function EmployeeDashboard() {
    const { user, logout } = useAuth();
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [selectedMonth, setSelectedMonth] = useState(12); // December
    const [selectedYear, setSelectedYear] = useState(2025); // 2025 - where data exists

    useEffect(() => {
        fetchAttendance();
    }, [selectedMonth, selectedYear]);

    const fetchAttendance = async () => {
        try {
            setLoading(true);
            const response = await api.getEmployeeAttendance({
                month: selectedMonth,
                year: selectedYear
            });
            setData(response);
        } catch (err) {
            console.error('Error fetching attendance:', err);
        } finally {
            setLoading(false);
        }
    };

    const months = [
        { value: 1, label: 'January' },
        { value: 2, label: 'February' },
        { value: 3, label: 'March' },
        { value: 4, label: 'April' },
        { value: 5, label: 'May' },
        { value: 6, label: 'June' },
        { value: 7, label: 'July' },
        { value: 8, label: 'August' },
        { value: 9, label: 'September' },
        { value: 10, label: 'October' },
        { value: 11, label: 'November' },
        { value: 12, label: 'December' }
    ];

    const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);

    const getHoursColor = (totalMinutes) => {
        const hours = totalMinutes / 60;
        if (hours >= 8) return 'text-green';
        if (hours >= 4) return 'text-amber';
        return 'text-red';
    };

    if (loading) {
        return (
            <div className="loading-overlay">
                <div className="loading-spinner"></div>
            </div>
        );
    }

    return (
        <div className="employee-dashboard">
            {/* Header */}
            <div className="employee-dashboard-header">
                <div>
                    <h1 className="page-title">Welcome, {data?.employee_name || user?.name || user?.email}</h1>
                    <p className="page-subtitle">Employee ID: {data?.employee_code || user?.employee_code || 'N/A'}</p>
                </div>
            </div>

            {/* Filters and Monthly Total */}
            <div className="employee-filter-section">
                <div className="employee-filters">
                    <div className="form-group">
                        <label htmlFor="month" className="form-label">Period:</label>
                        <select
                            id="month"
                            className="form-input form-select"
                            value={selectedMonth}
                            onChange={(e) => setSelectedMonth(Number(e.target.value))}
                        >
                            {months.map((month) => (
                                <option key={month.value} value={month.value}>
                                    {month.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <select
                            className="form-input form-select"
                            value={selectedYear}
                            onChange={(e) => setSelectedYear(Number(e.target.value))}
                        >
                            {years.map((year) => (
                                <option key={year} value={year}>
                                    {year}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                <div className="monthly-total-badge">
                    Monthly Total: <strong>{data?.monthly_total_hours || '0h 0m'}</strong>
                </div>
            </div>

            {/* Attendance Table */}
            <div className="employee-table-container">
                <table className="employee-table">
                    <thead>
                        <tr>
                            <th>DATE</th>
                            <th>FIRST IN</th>
                            <th>LAST OUT</th>
                            <th>TOTAL OFFICE HOURS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data?.records && data.records.length > 0 ? (
                            data.records.map((record, index) => (
                                <tr key={index}>
                                    <td>
                                        <div className="date-cell">
                                            <div className="date-primary">
                                                {new Date(record.date).toLocaleDateString('en-US', {
                                                    month: 'short',
                                                    day: 'numeric',
                                                    year: 'numeric'
                                                })}
                                            </div>
                                            <div className="date-secondary">{record.day}</div>
                                        </div>
                                    </td>
                                    <td>{record.first_in || '-'}</td>
                                    <td>{record.last_out || '-'}</td>
                                    <td>
                                        <span className={getHoursColor(record.total_minutes)}>
                                            {record.total_hours}
                                        </span>
                                    </td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="4" className="empty-message">
                                    No attendance records found for this period.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
