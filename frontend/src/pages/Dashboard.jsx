import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Users,
    UserCheck,
    ShieldCheck,
    ShieldX,
    AlertTriangle,
    Calendar,
    X
} from 'lucide-react';
import {
    PieChart,
    Pie,
    Cell,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from 'recharts';
import api from '../api/client';
import SummaryCard from '../components/SummaryCard';
import StatusBadge from '../components/StatusBadge';
import {
    getCurrentISOWeek,
    generateISOWeeks,
    isoWeekToDateString,
    getYearRange,
} from '../utils/isoWeek';

const COLORS = {
    GREEN: '#10b981',
    AMBER: '#f59e0b',
    RED: '#ef4444',
    BLUE: '#3b82f6',
    GRAY: '#9ca3af'
};

export default function Dashboard() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState(null);
    const [complianceStats, setComplianceStats] = useState(null);
    const [error, setError] = useState(null);

    // Calendar-based year + week selection
    const currentISO = getCurrentISOWeek();
    const [selectedYear, setSelectedYear] = useState(currentISO.year);
    const [selectedWeekValue, setSelectedWeekValue] = useState(
        `${currentISO.year}-W${String(currentISO.week).padStart(2, '0')}`
    );

    // Generate ISO weeks for the selected year (calendar-driven, never from DB)
    const years = useMemo(() => getYearRange(), []);
    const isoWeeks = useMemo(() => generateISOWeeks(selectedYear), [selectedYear]);

    // Chart & modal state
    const [chartData, setChartData] = useState([]);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalLoading, setModalLoading] = useState(false);
    const [modalData, setModalData] = useState({ title: '', employees: [] });

    // Convert ISO week value to YYYY-MM-DD for API calls
    const weekStartDate = useMemo(
        () => isoWeekToDateString(selectedWeekValue),
        [selectedWeekValue]
    );

    // Fetch dashboard summary once on mount
    useEffect(() => {
        fetchSummary();
    }, []);

    // Fetch chart + compliance data whenever week selection changes
    useEffect(() => {
        if (weekStartDate) {
            fetchChartData();
            fetchComplianceStats();
        }
    }, [weekStartDate]);

    const fetchSummary = async () => {
        try {
            setLoading(true);
            const dashboardData = await api.getDashboardSummary();
            setSummary(dashboardData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchChartData = async () => {
        try {
            const params = weekStartDate ? { week_start: weekStartDate } : {};
            const data = await api.getDashboardStats(params);
            if (data && data.stats) {
                setChartData(data.stats);
            } else {
                setChartData([]);
            }
        } catch (err) {
            console.error('Error fetching chart stats:', err);
            setChartData([]);
        }
    };

    const fetchComplianceStats = async () => {
        try {
            const params = weekStartDate ? { week_start: weekStartDate } : {};
            const data = await api.getWeeklyComplianceStats(params);
            setComplianceStats(data);
        } catch (err) {
            console.error('Error fetching compliance stats:', err);
            setComplianceStats(null);
        }
    };

    // When year changes, auto-select the first week of that year
    // (or current week if it's the current year)
    const handleYearChange = (newYear) => {
        setSelectedYear(newYear);
        if (newYear === currentISO.year) {
            setSelectedWeekValue(
                `${currentISO.year}-W${String(currentISO.week).padStart(2, '0')}`
            );
        } else {
            setSelectedWeekValue(`${newYear}-W01`);
        }
    };

    const handleBarClick = async (data, type) => {
        if (!data) return;
        try {
            setModalLoading(true);
            setModalOpen(true);
            const dateStr = data.date;
            setModalData({
                title: `${type} Employees - ${new Date(dateStr).toLocaleDateString()}`,
                employees: []
            });
            const details = await api.getDailyDetails({ date: dateStr, status: type });
            setModalData({
                title: `${type} Employees - ${new Date(dateStr).toLocaleDateString()}`,
                employees: details
            });
        } catch (err) {
            console.error('Error fetching details:', err);
            setModalData({ title: 'Error', employees: [] });
        } finally {
            setModalLoading(false);
        }
    };

    // Pie chart data
    const pieData = complianceStats ? [
        { name: 'Compliance', value: complianceStats.compliant_employees || 0, color: COLORS.GREEN },
        { name: 'Mid-Compliance', value: complianceStats.partial_compliant_employees || 0, color: COLORS.AMBER },
        { name: 'Non-Compliance', value: complianceStats.non_compliant_employees || 0, color: COLORS.RED }
    ].filter(d => d.value > 0) : [];
    

    // Week label for the subtitle
    const selectedWeekObj = isoWeeks.find(w => w.value === selectedWeekValue);

    if (loading) {
        return (
            <div className="loading-overlay">
                <div className="loading-spinner"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="empty-state">
                <AlertTriangle size={64} style={{ color: 'var(--color-status-amber)' }} />
                <h2 className="empty-state-title">Unable to load dashboard</h2>
                <p className="empty-state-text">{error}</p>
                <button className="btn btn-primary" onClick={fetchSummary}>
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div className="animate-fade-in" style={{ position: 'relative' }}>
            {/* Page Header */}
            <div className="page-header">
                <div className="flex justify-between items-center" style={{ width: '100%' }}>
                    <div>
                        <h1 className="page-title">Dashboard</h1>
                        <p className="page-subtitle">
                            {selectedWeekObj
                                ? `${selectedWeekObj.label}`
                                : 'Attendance Overview'}
                        </p>
                    </div>

                    {/* Year + Week Filters */}
                    <div className="flex items-center gap-2">
                        <Calendar size={18} className="text-muted" />
                        <select
                            className="form-input form-select"
                            value={selectedYear}
                            onChange={(e) => handleYearChange(Number(e.target.value))}
                            style={{ width: '100px' }}
                        >
                            {years.map((y) => (
                                <option key={y} value={y}>{y}</option>
                            ))}
                        </select>
                        <select
                            className="form-input form-select"
                            value={selectedWeekValue}
                            onChange={(e) => setSelectedWeekValue(e.target.value)}
                            style={{ width: '300px' }}
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

            {/* Summary Cards – Weekly Compliance Stats */}
            <div className="summary-cards">
                <SummaryCard
                    icon={Users}
                    value={complianceStats?.total_employees ?? summary?.total_employees ?? 0}
                    label="Total Employees"
                    description="All employees registered in the system."
                    onClick={() => navigate(`/employees${weekStartDate ? `?week_start=${weekStartDate}` : ''}`)}
                />
                <SummaryCard
                    icon={UserCheck}
                    value={complianceStats?.non_exempt_employees ?? 0}
                    label="Non-Exempted Employees"
                    description="WFO + Hybrid employees (excludes WFH)."
                    onClick={() => navigate(`/employees?filter=non_exempt${weekStartDate ? `&week_start=${weekStartDate}` : ''}`)}
                />
                <SummaryCard
                    icon={ShieldCheck}
                    value={complianceStats?.compliant_employees ?? 0}
                    label="Compliant to WFO Policy"
                    description="Non-exempt employees meeting WFO policy (≥90%)."
                    status="green"
                    onClick={() => navigate(`/employees?filter=compliant${weekStartDate ? `&week_start=${weekStartDate}` : ''}`)}
                />
                <SummaryCard
                    icon={ShieldX}
                    value={complianceStats?.non_compliant_employees ?? 0}
                    label="Non-Compliant to WFO Policy"
                    description="Non-exempt employees below WFO policy (<90%)."
                    status="red"
                    onClick={() => navigate(`/employees?filter=non_compliant${weekStartDate ? `&week_start=${weekStartDate}` : ''}`)}
                />
            </div>

            {/* Charts */}
            <div className="charts-grid">
                {/* Daily Attendance (WFO vs WFH) */}
                <div className="chart-container">
                    <div className="chart-header">
                        <h3 className="chart-title">Daily Attendance (WFO vs WFH)</h3>
                        <span className="text-muted text-xs">Click bars to see details</span>
                    </div>
                    {chartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                                <XAxis dataKey="day" stroke="var(--color-text-muted)" fontSize={12} />
                                <YAxis stroke="var(--color-text-muted)" fontSize={12} />
                                <Tooltip
                                    contentStyle={{
                                        background: 'var(--color-surface)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: '8px'
                                    }}
                                    cursor={{ fill: 'var(--color-bg-subtle)' }}
                                />
                                <Legend />
                                <Bar
                                    dataKey="wfo"
                                    name="Work From Office"
                                    stackId="a"
                                    fill={COLORS.GREEN}
                                    radius={[0, 0, 4, 4]}
                                    onClick={(data) => handleBarClick(data, 'WFO')}
                                    style={{ cursor: 'pointer' }}
                                />
                                <Bar
                                    dataKey="wfh"
                                    name="WFH / Absent"
                                    stackId="a"
                                    fill={COLORS.GRAY}
                                    radius={[4, 4, 0, 0]}
                                    onClick={(data) => handleBarClick(data, 'WFH')}
                                    style={{ cursor: 'pointer' }}
                                />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="empty-state" style={{ padding: 'var(--spacing-8)' }}>
                            <p className="text-muted">No attendance data for this week</p>
                        </div>
                    )}
                </div>

                {/* Compliance Distribution */}
                <div className="chart-container">
                    <div className="chart-header">
                        <h3 className="chart-title">Compliance Distribution</h3>
                    </div>
                    {pieData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={250}>
                            <PieChart>
                                <Pie
                                    data={pieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={100}
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {pieData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    contentStyle={{
                                        background: '#1e293b',
                                        border: '1px solid #334155',
                                        borderRadius: '8px',
                                        color: '#ffffff'
                                    }}
                                    itemStyle={{ color: '#ffffff' }}
                                    labelStyle={{ color: '#94a3b8' }}
                                />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="empty-state" style={{ padding: 'var(--spacing-8)' }}>
                            <p className="text-muted">No compliance data available</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Drill Down Modal */}
            {modalOpen && (
                <div className="modal-overlay" style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <div className="modal-content" style={{
                        background: 'var(--color-surface)',
                        borderRadius: 'var(--radius-lg)',
                        width: '90%', maxWidth: '800px',
                        maxHeight: '90vh', display: 'flex', flexDirection: 'column',
                        boxShadow: 'var(--shadow-xl)'
                    }}>
                        <div className="modal-header" style={{
                            padding: 'var(--spacing-4)',
                            borderBottom: '1px solid var(--color-border)',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}>
                            <h3 className="font-bold text-lg">{modalData.title}</h3>
                            <button
                                onClick={() => setModalOpen(false)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
                            >
                                <X size={24} />
                            </button>
                        </div>

                        <div className="modal-body" style={{ padding: '0', overflowY: 'auto', flex: 1 }}>
                            {modalLoading ? (
                                <div className="p-8 text-center">
                                    <div className="loading-spinner mb-2"></div>
                                    <p className="text-muted">Loading details...</p>
                                </div>
                            ) : (
                                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead style={{ background: 'var(--color-bg-subtle)', position: 'sticky', top: 0 }}>
                                        <tr>
                                            <th style={{ padding: '12px', textAlign: 'left' }}>Employee</th>
                                            <th style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                                            <th style={{ padding: '12px', textAlign: 'left' }}>Hours</th>
                                            <th style={{ padding: '12px', textAlign: 'left' }}>In / Out</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {modalData.employees.length > 0 ? (
                                            modalData.employees.map((emp) => (
                                                <tr
                                                    key={emp.employee_code}
                                                    onClick={() => navigate(`/employee/${emp.employee_code}`)}
                                                    style={{
                                                        borderBottom: '1px solid var(--color-border)',
                                                        cursor: 'pointer',
                                                        transition: 'background 0.2s'
                                                    }}
                                                    className="hover:bg-slate-50 dark:hover:bg-slate-800"
                                                >
                                                    <td style={{ padding: '12px' }}>
                                                        <div className="font-medium">{emp.employee_name}</div>
                                                        <div className="text-sm text-muted">ID: {emp.employee_code}</div>
                                                    </td>
                                                    <td style={{ padding: '12px' }}>
                                                        <StatusBadge status={emp.status} />
                                                    </td>
                                                    <td style={{ padding: '12px' }}>{emp.hours}</td>
                                                    <td style={{ padding: '12px' }}>
                                                        {(emp.in_time && emp.out_time && emp.in_time !== '-' && emp.out_time !== '-')
                                                            ? `${emp.in_time} - ${emp.out_time}`
                                                            : '-'}
                                                    </td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan="4" style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                                                    No employees found for this category.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
