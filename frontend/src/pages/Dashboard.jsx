import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Users,
    Clock,
    Building2,
    AlertTriangle,
    TrendingUp,
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
import DataTable from '../components/DataTable';

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
    const [employees, setEmployees] = useState([]);
    const [error, setError] = useState(null);

    // New State for Chart & Modal
    const [weeks, setWeeks] = useState([]);
    const [selectedWeek, setSelectedWeek] = useState('');
    const [chartData, setChartData] = useState([]);
    const [modalOpen, setModalOpen] = useState(false);
    const [modalLoading, setModalLoading] = useState(false);
    const [modalData, setModalData] = useState({ title: '', employees: [] });

    useEffect(() => {
        fetchInitialData();
    }, []);

    useEffect(() => {
        if (selectedWeek || weeks.length > 0) {
            fetchChartData();
        }
    }, [selectedWeek, weeks]);

    const fetchInitialData = async () => {
        try {
            setLoading(true);
            const [dashboardData, employeesData, weeksData] = await Promise.all([
                api.getDashboardSummary(),
                api.getAllEmployeesReport({ sort_by: 'compliance', sort_order: 'asc' }),
                api.getAvailableWeeks()
            ]);

            setSummary(dashboardData);
            setEmployees(employeesData.employees || []);
            setWeeks(weeksData.weeks || []);

            // Set default week if available
            if (weeksData.weeks && weeksData.weeks.length > 0 && !selectedWeek) {
                setSelectedWeek(weeksData.weeks[0].week_start);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchChartData = async () => {
        try {
            const params = selectedWeek ? { week_start: selectedWeek } : {};
            const data = await api.getDashboardStats(params);
            if (data && data.stats) {
                setChartData(data.stats);
            }
        } catch (err) {
            console.error('Error fetching chart stats:', err);
        }
    };

    const handleBarClick = async (data, type) => {
        if (!data) return;
        try {
            setModalLoading(true);
            setModalOpen(true);
            // type is 'WFO' or 'WFH'
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

    const columns = [
        {
            key: 'employee_name',
            label: 'Employee',
            sortable: true,
            render: (value, row) => (
                <div className="cell-employee">
                    <div className="employee-avatar">
                        {value?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                    </div>
                    <div className="employee-info">
                        <span className="employee-name">{value}</span>
                        <span className="employee-code">ID: {row.employee_code}</span>
                    </div>
                </div>
            )
        },
        {
            key: 'total_office_hours',
            label: 'Office Hours',
            sortable: true
        },
        {
            key: 'wfo_days',
            label: 'WFO Days',
            sortable: true
        },
        {
            key: 'compliance_percentage',
            label: 'Compliance',
            sortable: true,
            render: (value, row) => (
                <div className="flex items-center gap-3">
                    <div className="progress-bar" style={{ width: '100px' }}>
                        <div
                            className={`progress-fill ${row.status?.toLowerCase()}`}
                            style={{ width: `${Math.min(value, 100)}%` }}
                        />
                    </div>
                    <span className="font-medium">{value?.toFixed(1)}%</span>
                </div>
            )
        },
        {
            key: 'status',
            label: 'Status',
            sortable: true,
            render: (value) => <StatusBadge status={value} />
        }
    ];

    // Prepare pie chart data
    const pieData = summary?.status_distribution ? [
        { name: 'Excellent', value: summary.status_distribution.GREEN, color: COLORS.GREEN },
        { name: 'Meets Target', value: summary.status_distribution.AMBER, color: COLORS.AMBER },
        { name: 'Below Target', value: summary.status_distribution.RED, color: COLORS.RED }
    ].filter(d => d.value > 0) : [];

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
                <button className="btn btn-primary" onClick={fetchInitialData}>
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
                            {selectedWeek && weeks.length > 0
                                ? (() => {
                                    const selectedWeekObj = weeks.find(w => w.week_start === selectedWeek);
                                    if (selectedWeekObj) {
                                        return `Week of ${new Date(selectedWeekObj.week_start).toLocaleDateString('en-US', {
                                            month: 'short',
                                            day: 'numeric'
                                        })} - ${new Date(selectedWeekObj.week_end).toLocaleDateString('en-US', {
                                            month: 'short',
                                            day: 'numeric',
                                            year: 'numeric'
                                        })}`;
                                    }
                                    return 'Attendance Overview';
                                })()
                                : 'Attendance Overview'}
                        </p>
                    </div>

                    {/* Week Filter */}
                    <div className="flex items-center gap-2">
                        <Calendar size={18} className="text-muted" />
                        <select
                            className="form-input form-select"
                            value={selectedWeek}
                            onChange={(e) => setSelectedWeek(e.target.value)}
                            style={{ width: '200px' }}
                        >
                            {weeks.map((week) => (
                                <option key={week.week_start} value={week.week_start}>
                                    {week.label}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="summary-cards">
                <SummaryCard
                    icon={Users}
                    value={summary?.total_employees || 0}
                    label="Total Employees"
                    description="Active employees in the system for this week."
                    onClick={() => {
                        setModalData({
                            title: 'All Employees',
                            employees: employees
                        });
                        setModalOpen(true);
                    }}
                />
                <SummaryCard
                    icon={TrendingUp}
                    value={`${summary?.avg_compliance?.toFixed(1) || 0}%`}
                    label="Average Compliance"
                    description="Overall adherence to WFO policy."
                    status={
                        (summary?.avg_compliance || 0) >= 90 ? 'green' :
                            (summary?.avg_compliance || 0) >= 60 ? 'amber' : 'red'
                    }
                />
                <SummaryCard
                    icon={Building2}
                    value={summary?.total_wfo_days || 0}
                    label="Total WFO Days"
                    description="Cumulative office days worked this week."
                    status="green"
                />
                <SummaryCard
                    icon={AlertTriangle}
                    value={summary?.alerts || 0}
                    label="Employees Below Target"
                    description="Employees with < 60% compliance (Non-Compliance)."
                    status="red"
                    onClick={() => {
                        const belowTarget = employees.filter(emp =>
                            emp.status?.toLowerCase() === 'red'
                        );
                        setModalData({
                            title: 'Employees Below Target',
                            employees: belowTarget
                        });
                        setModalOpen(true);
                    }}
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

            {/* Employees Table */}
            <div className="table-container mt-8">
                <div className="table-header">
                    <h3 className="table-title">Employee Attendance Overview</h3>
                    <div className="table-actions">
                        <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => navigate('/employees')}
                        >
                            View All
                        </button>
                    </div>
                </div>
                <DataTable
                    columns={columns}
                    data={employees.slice(0, 5)}
                    onRowClick={(row) => navigate(`/employee/${row.employee_code}`)}
                    emptyMessage="No employee data yet. Upload attendance data to see reports."
                />
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
