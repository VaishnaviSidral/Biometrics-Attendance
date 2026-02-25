import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    ArrowLeft,
    Download,
    Clock,
    Calendar,
    TrendingUp,
    Building2
} from 'lucide-react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer
} from 'recharts';
import api from '../api/client';
import SummaryCard from '../components/SummaryCard';
import StatusBadge, { statusToCssClass } from '../components/StatusBadge';
import DataTable from '../components/DataTable';
import { useViewMonthDate } from '../contexts/DateContext';

export default function IndividualReport() {
    const { code } = useParams();
    const navigate = useNavigate();
    const { monthYear, monthValue, setMonthYear, setMonthValue } = useViewMonthDate('individualReport');
    const [loading, setLoading] = useState(true);
    const [report, setReport] = useState(null);
    const [activeTab, setActiveTab] = useState('daily');

    const now = new Date();
    const selectedYear = monthYear;
    const selectedMonth = monthValue;
    const setSelectedYear = setMonthYear;
    const setSelectedMonth = setMonthValue;

    useEffect(() => {
        fetchData();
    }, [code, selectedYear, selectedMonth]);    

    const fetchData = async () => {
        try {
            setLoading(true);
    
            const startDate = new Date(selectedYear, selectedMonth - 1, 1);
            const endDate = new Date(selectedYear, selectedMonth, 0); // last day of month
    
            const params = {
                start_date: startDate.toISOString().split('T')[0],
                end_date: endDate.toISOString().split('T')[0]
            };
    
            const data = await api.getIndividualReport(code, params);
            setReport(data);
        } catch (err) {
            console.error('Error fetching report:', err);
        } finally {
            setLoading(false);
        }
    };
    

    const handleExport = async () => {
        try {
            const startDate = new Date(selectedYear, selectedMonth - 1, 1);
            const endDate = new Date(selectedYear, selectedMonth, 0);
    
            const params = {
                start_date: startDate.toISOString().split('T')[0],
                end_date: endDate.toISOString().split('T')[0]
            };
    
            await api.exportIndividual(code, params);
        } catch (err) {
            console.error('Export error:', err);
        }
    };
    

    const dailyColumns = [
        {
            key: 'date',
            label: 'Date',
            render: (value, row) => (
                <div>
                    <div className="font-medium">{new Date(value).toLocaleDateString()}</div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>{row.day}</div>
                </div>
            )
        },
        {
            key: 'first_in',
            label: 'First In',
            render: (value) => value || '-'
        },
        {
            key: 'last_out',
            label: 'Last Out',
            render: (value) => value || '-'
        },
        {
            key: 'total_hours',
            label: 'Total Hours',
            render: (value, row) => (
                <span className={row.total_minutes > 0 ? 'text-green' : 'text-muted'}>
                    {value}
                </span>
            )
        },
        // {
        //     key: 'status',
        //     label: 'Status',
        //     render: (value) => {
        //         const colors = {
        //             PRESENT: 'green',
        //             PARTIAL: 'amber',
        //             ABSENT: 'red'
        //         };
        //         const labels = {
        //             PRESENT: 'Present',
        //             PARTIAL: 'Partial',
        //             ABSENT: 'Absent'
        //         };
        //         return (
        //             <span className={`font-medium text-${colors[value] || 'red'}`}>
        //                 {labels[value] || value}
        //             </span>
        //         );
        //     }
        // },
        {
            key: 'daily_compliance',
            label: 'Daily Compliance',
            render: (value, row) => {
                // Use the status string directly from backend (Compliance / Mid-Compliance / Non-Compliance)
                const status = row.daily_status_color || 'Non-Compliance';
                const isWeekend = row.day === 'Saturday' || row.day === 'Sunday';
                return (
                    <div className="flex items-center gap-2">
                        {!isWeekend && (
                        <>
                            <span className="font-medium">
                                {value?.toFixed(1) || 0}%
                            </span>
                            <StatusBadge status={status} />
                        </>
                    )}
                    </div>
                );
            }
        }
    ];

    const weeklyColumns = [
        {
            key: 'week_label',
            label: 'Week',
            render: (value) => <span className="font-medium">{value}</span>
        },
        {
            key: 'wfo_days',
            label: 'WFO Days',
            render: (value, row) => (
                <span>
                    <span className="font-medium">{value}</span>
                    <span className="text-muted"> / {row.required_wfo_days}</span>
                </span>
            )
        },
        {
            key: 'total_hours',
            label: 'Total Hours'
        },
        {
            key: 'compliance_percentage',
            label: 'Compliance',
            render: (value, row) => (
                <div className="flex items-center gap-3">
                    <div className="progress-bar" style={{ width: '80px' }}>
                        <div
                            className={`progress-fill ${statusToCssClass(row.status)}`}
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
            render: (value) => <StatusBadge status={value} />
        }
    ];

    if (loading) {
        return (
            <div className="loading-overlay">
                <div className="loading-spinner"></div>
            </div>
        );
    }

    if (!report && !loading) {
        return (
            <div className="empty-state">
                <h2 className="empty-state-title">Employee not found</h2>
                <p className="empty-state-text">The requested employee report could not be found.</p>
                <button className="btn btn-primary" onClick={() => navigate('/employees')}>
                    Back to Employees
                </button>
            </div>
        );
    }

    // Prepare chart data
    const chartData = report?.weekly_summaries?.map(w => ({
        week: w.week_label?.split(' ')[0] + ' ' + w.week_label?.split(' ')[1],
        compliance: w.compliance_percentage
    })).reverse() || [];

    return (
        <div className="animate-fade-in">
            {/* Back Button & Header */}
            <div className="flex items-center gap-4 mb-6">
                <button
                    className="btn btn-ghost btn-icon"
                    onClick={() => navigate('/employees')}
                >
                    <ArrowLeft size={20} />
                </button>
                <div className="flex-1">
                    <h1 className="page-title">{report?.employee?.name}</h1>
                    <p className="page-subtitle">
                        • Employee ID: {report?.employee?.code}
                        {report?.employee?.work_mode && ` • Work Mode: ${report?.employee?.work_mode}`}
                    </p>
                </div>

                {/* Year + Month Filter */}
                <div className="flex items-center gap-4">

                {/* Year */}
                <select
                    className="form-input form-select"
                    value={selectedYear}
                    onChange={(e) => setSelectedYear(Number(e.target.value))}
                >
                    {Array.from({ length: 6 }, (_, i) => {
                        const y = now.getFullYear() - i;
                        return (
                            <option key={y} value={y}>
                                {y}
                            </option>
                        );
                    })}
                </select>

                {/* Month */}
                <select
                    className="form-input form-select"
                    value={selectedMonth}
                    onChange={(e) => setSelectedMonth(Number(e.target.value))}
                >
                    {[
                        'January','February','March','April','May','June',
                        'July','August','September','October','November','December'
                    ].map((m, i) => (
                        <option key={i+1} value={i+1}>
                            {m}
                        </option>
                    ))}
                </select>

                {/* Export (optional) */}
                {/* 
                <button className="btn btn-primary" onClick={handleExport}>
                    <Download size={18} />
                    Export Report
                </button> 
                */}
                </div>


                {/* <button className="btn btn-primary" onClick={handleExport}>
                    <Download size={18} />
                    Export Report
                </button> */}
            </div>

            {/* Summary Cards */}
            <div className="summary-cards">
                <SummaryCard
                    icon={Clock}
                    value={report?.summary?.total_office_hours || '0h 0m'}
                    label="Total Office Hours"
                />
                <SummaryCard
                    icon={Building2}
                    value={report?.summary?.total_wfo_days || 0}
                    label="WFO Days"
                    status="green"
                />
                <SummaryCard
                    icon={TrendingUp}
                    value={`${report?.summary?.avg_compliance?.toFixed(1) || 0}%`}
                    label="Average Compliance"
                    status={statusToCssClass(report?.summary?.overall_status)}
                />
                <SummaryCard
                    icon={Calendar}
                    value={report?.daily_records?.length || 0}
                    label="Days Recorded"
                />
            </div>

            {/* Weekly Trend Chart */}
            {chartData.length > 0 && (
                <div className="chart-container mb-8">
                    <div className="chart-header">
                        <h3 className="chart-title">Compliance Trend</h3>
                    </div>
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                            <XAxis
                                dataKey="week"
                                stroke="var(--color-text-muted)"
                                fontSize={12}
                            />
                            <YAxis
                                stroke="var(--color-text-muted)"
                                fontSize={12}
                                domain={[0, 100]}
                            />
                            <Tooltip
                                contentStyle={{
                                    background: 'var(--color-surface)',
                                    border: '1px solid var(--color-border)',
                                    borderRadius: '8px'
                                }}
                                formatter={(value) => [`${value}%`, 'Compliance']}
                            />
                            <Line
                                type="monotone"
                                dataKey="compliance"
                                stroke="var(--color-primary)"
                                strokeWidth={3}
                                dot={{ fill: 'var(--color-primary)', r: 6 }}
                                activeDot={{ r: 8 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}

            {/* Tabs */}
            <div className="tabs">
                <button
                    className={`tab ${activeTab === 'daily' ? 'active' : ''}`}
                    onClick={() => setActiveTab('daily')}
                >
                    Daily Records
                </button>
                <button
                    className={`tab ${activeTab === 'weekly' ? 'active' : ''}`}
                    onClick={() => setActiveTab('weekly')}
                >
                    Weekly Summaries
                </button>
            </div>

            {/* Data Tables */}
            <div className="table-container">
                <DataTable
                    columns={activeTab === 'daily' ? dailyColumns : weeklyColumns}
                    data={activeTab === 'daily' ? report?.daily_records : report?.weekly_summaries}
                    emptyMessage={`No ${activeTab} records found for this employee.`}
                />
            </div>
        </div>
    );
}
