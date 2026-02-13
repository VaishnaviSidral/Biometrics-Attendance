import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Download, Search } from 'lucide-react';
import api from '../api/client';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';

export default function AllEmployees() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState(true);
    const [employees, setEmployees] = useState([]);
    const [weeks, setWeeks] = useState([]);
    const [selectedWeek, setSelectedWeek] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [searchTerm, setSearchTerm] = useState(searchParams.get('search') || '');
    const [sortBy, setSortBy] = useState('name');
    const [sortOrder, setSortOrder] = useState('asc');

    // Work mode tab: '' = All, 'WFO', 'HYBRID', 'WFH'
    const [workModeTab, setWorkModeTab] = useState('');

    useEffect(() => {
        fetchData();
    }, [selectedWeek, sortBy, sortOrder]);

    const fetchData = async () => {
        try {
            setLoading(true);
            const params = {
                sort_by: sortBy,
                sort_order: sortOrder
            };

            if (selectedWeek) params.week_start = selectedWeek;

            const data = await api.getAllEmployeesReport(params);
            setEmployees(data.employees || []);
            setWeeks(data.available_weeks || []);
        } catch (err) {
            console.error('Error fetching employees:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        try {
            await api.exportAllEmployees(selectedWeek);
        } catch (err) {
            console.error('Export error:', err);
        }
    };

    // Filter employees based on search, status, and work mode tab
    const filteredEmployees = employees.filter(emp => {
        // Search filter
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            const matchesSearch = (
                emp.employee_name?.toLowerCase().includes(term) ||
                emp.employee_code?.toLowerCase().includes(term)
            );
            if (!matchesSearch) return false;
        }

        // Work mode tab filter
        if (workModeTab) {
            if ((emp.work_mode || 'WFO') !== workModeTab) return false;
        }

        // Status filter
        if (statusFilter) {
            if (statusFilter === 'compliant') {
                return emp.status !== 'RED';
            } else if (statusFilter === 'RED') {
                return emp.status === 'RED';
            } else {
                return emp.status === statusFilter;
            }
        }

        return true;
    });

    // Work mode counts
    const wfoCount = employees.filter(e => (e.work_mode || 'WFO') === 'WFO').length;
    const hybridCount = employees.filter(e => (e.work_mode || 'WFO') === 'HYBRID').length;
    const wfhCount = employees.filter(e => (e.work_mode || 'WFO') === 'WFH').length;

    // Columns change based on work mode tab
    const getColumns = () => {
        const baseColumns = [
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
            }
        ];

        if (workModeTab === 'WFH') {
            // WFH: Employee, Total hours, Compliance (100%), Status
            return [
                ...baseColumns,
                {
                    key: 'total_office_hours',
                    label: 'Total Hours',
                    sortable: true
                },
                {
                    key: 'compliance_percentage',
                    label: 'Compliance',
                    sortable: true,
                    render: () => (
                        <div className="flex items-center gap-3">
                            <div className="progress-bar" style={{ width: '80px' }}>
                                <div
                                    className="progress-fill green"
                                    style={{ width: '100%' }}
                                />
                            </div>
                            <span className="font-medium">100.0%</span>
                        </div>
                    )
                },
                {
                    key: 'status',
                    label: 'Status',
                    sortable: true,
                    render: () => <StatusBadge status="GREEN" />
                }
            ];
        }

        // WFO and Hybrid tabs
        const requiredDays = workModeTab === 'HYBRID' ? 3 : 5;

        return [
            ...baseColumns,
            {
                key: 'total_office_hours',
                label: 'Total Hours',
                sortable: true
            },
            {
                key: 'wfo_days',
                label: 'Days',
                sortable: true,
                render: (value, row) => (
                    <span>
                        <span className="font-medium">{value}</span>
                        <span className="text-muted"> / {row.required_wfo_days || requiredDays}</span>
                    </span>
                )
            },
            {
                key: 'expected_hours',
                label: 'Expected Hours',
                sortable: false
            },
            {
                key: 'compliance_percentage',
                label: 'Compliance',
                sortable: true,
                render: (value, row) => (
                    <div className="flex items-center gap-3">
                        <div className="progress-bar" style={{ width: '80px' }}>
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
    };

    // Default columns (All tab) includes work_mode column
    const allColumns = [
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
            key: 'work_mode',
            label: 'Mode',
            sortable: true,
            render: (value) => {
                const colors = { WFO: '#3b82f6', HYBRID: '#8b5cf6', WFH: '#06b6d4' };
                return (
                    <span style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: 'var(--font-size-xs)',
                        fontWeight: 600,
                        background: `${colors[value] || colors.WFO}20`,
                        color: colors[value] || colors.WFO
                    }}>
                        {value || 'WFO'}
                    </span>
                );
            }
        },
        {
            key: 'total_office_hours',
            label: 'Total Hours',
            sortable: true
        },
        {
            key: 'wfo_days',
            label: 'Days',
            sortable: true,
            render: (value, row) => (
                <span>
                    <span className="font-medium">{value}</span>
                    <span className="text-muted"> / {row.required_wfo_days}</span>
                </span>
            )
        },
        {
            key: 'expected_hours',
            label: 'Expected',
            sortable: false
        },
        {
            key: 'compliance_percentage',
            label: 'Compliance',
            sortable: true,
            render: (value, row) => (
                <div className="flex items-center gap-3">
                    <div className="progress-bar" style={{ width: '80px' }}>
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

    const columns = workModeTab ? getColumns() : allColumns;

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <h1 className="page-title">All Employees Report</h1>
                <p className="page-subtitle">
                    View and analyze attendance data for all employees
                </p>
            </div>

            {/* Filters */}
            <div className="card mb-6">
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 'var(--spacing-4)',
                    alignItems: 'end'
                }}>
                    {/* Search */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Name</label>
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
                                className="form-input"
                                placeholder="Search by name or ID..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                style={{ paddingLeft: '40px' }}
                            />
                        </div>
                    </div>

                    {/* Week Filter */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Week</label>
                        <select
                            className="form-input form-select"
                            value={selectedWeek}
                            onChange={(e) => setSelectedWeek(e.target.value)}
                        >
                            <option value="">Latest Week</option>
                            {weeks.map((week) => (
                                <option key={week.week_start} value={week.week_start}>
                                    {week.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Status Filter */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Status</label>
                        <select
                            className="form-input form-select"
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                        >
                            <option value="">All Status</option>
                            <option value="GREEN">Compliance (&ge;90%)</option>
                            <option value="AMBER">Mid-Compliance (60-89%)</option>
                            <option value="RED">Non-Compliance (&lt;60%)</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Stats Summary */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 'var(--spacing-4)',
                marginBottom: 'var(--spacing-6)'
            }}>
                <div
                    className="card"
                    style={{ textAlign: 'center', padding: 'var(--spacing-4)', cursor: 'pointer' }}
                    onClick={() => setStatusFilter('')}
                >
                    <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 'bold' }}>
                        {employees.length}
                    </div>
                    <div className="text-muted">Total Employees</div>
                </div>

                <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-4)' }}>
                    <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 'bold', color: 'var(--color-primary)' }}>
                        {(filteredEmployees.reduce((acc, emp) => acc + emp.compliance_percentage, 0) / (filteredEmployees.length || 1)).toFixed(1)}%
                    </div>
                    <div className="text-muted">Avg Compliance</div>
                </div>

                <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-4)', background: 'var(--color-status-green-bg)', borderColor: 'var(--color-status-green-border)' }}>
                    <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 'bold', color: 'var(--color-status-green)' }}>
                        {filteredEmployees.filter(e => e.compliance_percentage >= 90).length}
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>Compliance (&ge;90%)</div>
                </div>

                <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-4)', background: 'var(--color-status-red-bg)', borderColor: 'var(--color-status-red-border)' }}>
                    <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 'bold', color: 'var(--color-status-red)' }}>
                        {filteredEmployees.filter(e => e.compliance_percentage < 60).length}
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>Non-Compliance (&lt;60%)</div>
                </div>
            </div>

            {/* Work Mode Tabs */}
            <div className="tabs" style={{ marginBottom: 'var(--spacing-4)' }}>
                <button
                    className={`tab ${workModeTab === '' ? 'active' : ''}`}
                    onClick={() => setWorkModeTab('')}
                >
                    All ({employees.length})
                </button>
                <button
                    className={`tab ${workModeTab === 'WFO' ? 'active' : ''}`}
                    onClick={() => setWorkModeTab('WFO')}
                    style={workModeTab === 'WFO' ? { borderColor: '#3b82f6', color: '#3b82f6' } : {}}
                >
                    WFO ({wfoCount})
                </button>
                <button
                    className={`tab ${workModeTab === 'HYBRID' ? 'active' : ''}`}
                    onClick={() => setWorkModeTab('HYBRID')}
                    style={workModeTab === 'HYBRID' ? { borderColor: '#8b5cf6', color: '#8b5cf6' } : {}}
                >
                    Hybrid ({hybridCount})
                </button>
                <button
                    className={`tab ${workModeTab === 'WFH' ? 'active' : ''}`}
                    onClick={() => setWorkModeTab('WFH')}
                    style={workModeTab === 'WFH' ? { borderColor: '#06b6d4', color: '#06b6d4' } : {}}
                >
                    WFH ({wfhCount})
                </button>
            </div>

            {/* Data Table */}
            <div className="table-container">
                <div className="table-header">
                    <h3 className="table-title">
                        {filteredEmployees.length} Employee{filteredEmployees.length !== 1 ? 's' : ''}
                        {workModeTab && ` (${workModeTab})`}
                    </h3>
                    <button className="btn btn-primary" onClick={handleExport}>
                        <Download size={18} />
                        Export CSV
                    </button>
                </div>
                <DataTable
                    columns={columns}
                    data={filteredEmployees}
                    loading={loading}
                    onRowClick={(row) => navigate(`/employee/${row.employee_code}`)}
                    emptyMessage="No employees found. Try adjusting your filters or upload attendance data."
                />
            </div>
        </div>
    );
}
