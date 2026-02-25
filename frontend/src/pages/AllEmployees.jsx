import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Download, Search } from 'lucide-react';
import api from '../api/client';
import DataTable from '../components/DataTable';
import StatusBadge, { statusToCssClass } from '../components/StatusBadge';
import { useViewWeekDate } from '../contexts/DateContext';
import {
    getCurrentISOWeek,
    generateISOWeeks,
    isoWeekToDateString,
    getYearRange,
    getISOYear,
    getISOWeekNumber,
} from '../utils/isoWeek';

export default function AllEmployees() {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const { weekYear, weekValue, setWeekYear, setWeekValue } = useViewWeekDate('allEmployees');
    const [loading, setLoading] = useState(true);
    const [complianceSettings, setComplianceSettings] = useState(null);
    const [employees, setEmployees] = useState([]);
    const [statusFilter, setStatusFilter] = useState('');
    const [searchTerm, setSearchTerm] = useState(searchParams.get('search') || '');
    const [sortBy, setSortBy] = useState('name');
    const [sortOrder, setSortOrder] = useState('asc');
    const [buHeads, setBuHeads] = useState([]);
    const [selectedBUHead, setSelectedBUHead] = useState('');
    const [employeeBUMap, setEmployeeBUMap] = useState({}); // employee_code → bu_head


    // Work mode tab: '' = All, 'WFO', 'HYBRID', 'WFH'
    const [workModeTab, setWorkModeTab] = useState('');

    // Dashboard navigation filter: 'non_exempt', 'compliant', 'non_compliant'
    const [dashboardFilter, setDashboardFilter] = useState(searchParams.get('filter') || '');

    // Calendar-based year + week (from global context)
    const currentISO = getCurrentISOWeek();
    const urlWeekStart = searchParams.get('week_start');

    // On mount, if URL has week_start, sync to context
    useEffect(() => {
        if (urlWeekStart) {
            const d = new Date(urlWeekStart + 'T00:00:00Z');
            const y = getISOYear(d);
            const w = getISOWeekNumber(d);
            setWeekYear(y);
            setWeekValue(`${y}-W${String(w).padStart(2, '0')}`);
        }
    }, []); // only on mount

    const selectedYear = weekYear;
    const selectedWeekValue = weekValue;
    const setSelectedYear = setWeekYear;
    const setSelectedWeekValue = setWeekValue;

    const years = useMemo(() => getYearRange(), []);
    const isoWeeks = useMemo(() => generateISOWeeks(selectedYear), [selectedYear]);

    // Convert ISO week to YYYY-MM-DD for API
    const weekStartDate = useMemo(
        () => isoWeekToDateString(selectedWeekValue),
        [selectedWeekValue]
    );

    // Fetch data when week or sort changes
    useEffect(() => {
        fetchData();
    }, [weekStartDate, sortBy, sortOrder]);

    useEffect(() => {
        // Fetch BU Heads list, employee-project-BU mapping, and compliance settings in parallel
        api.getBUHeads()
            .then(setBuHeads)
            .catch(err => console.error('Error fetching BU heads:', err));

        api.getEmployeesWithProjectBU()
            .then(data => {
                // Build map: employee_code → bu_head
                // An employee may appear in multiple projects; take the first non-N/A
                const map = {};
                for (const row of data) {
                    const code = row.employee_code;
                    if (!map[code] || map[code] === 'N/A') {
                        map[code] = row.bu_head || 'N/A';
                    }
                }
                setEmployeeBUMap(map);
            })
            .catch(err => console.error('Error fetching employee BU mapping:', err));

        api.getSettings()
            .then(setComplianceSettings)
            .catch(err => console.error('Error fetching settings:', err));
    }, []);
    
    const fetchData = async () => {
        try {
            setLoading(true);
            const params = {
                sort_by: sortBy,
                sort_order: sortOrder
            };
            if (weekStartDate) params.week_start = weekStartDate;

            const data = await api.getAllEmployeesReport(params);
            setEmployees(data.employees || []);
        } catch (err) {
            console.error('Error fetching employees:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        try {
            await api.exportAllEmployees({
                week_start: weekStartDate || undefined,
                work_mode: workModeTab || undefined,
                status_filter: statusFilter || undefined,
                sort_by: sortBy || undefined,
                sort_order: sortOrder || undefined
            });
        } catch (err) {
            console.error('Export error:', err);
        }
    };

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

    // Clear dashboard filter
    const clearDashboardFilter = () => {
        if (dashboardFilter) {
            setDashboardFilter('');
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('filter');
            setSearchParams(newParams, { replace: true });
        }
    };

    // Filter employees based on search, status, work mode tab, and dashboard filter
    const filteredEmployees = employees.filter(emp => {
        // Dashboard navigation filter
        if (dashboardFilter) {
            const empWorkMode = (emp.work_mode || 'WFO').toUpperCase();
            if (dashboardFilter === 'non_exempt') {
                if (empWorkMode === 'WFH') return false;
            } else             if (dashboardFilter === 'compliant') {
                if (empWorkMode === 'WFH') return false;
                if (emp.status !== 'Compliance') return false;
            } else if (dashboardFilter === 'non_compliant') {
                if (empWorkMode === 'WFH') return false;
                if (emp.status === 'Compliance') return false;
            }
        }

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
            if (emp.status !== statusFilter) return false;
        }

        // BU Head filter
        if (selectedBUHead) {
            const empBU = employeeBUMap[emp.employee_code] || 'N/A';
            if (empBU !== selectedBUHead) return false;
        }

        return true;
    });

    // Avg Compliance excluding WFH
    const avgCompliance = (() => {
        const eligible = filteredEmployees.filter(
            emp => (emp.work_mode || 'WFO') !== 'WFH'
        );

        if (!eligible.length) return '0.0';

        const total = eligible.reduce(
            (acc, emp) => acc + (emp.compliance_percentage || 0),
            0
        );

        return (total / eligible.length).toFixed(1);
    })();
    // Work mode counts
    const wfoCount = employees.filter(e => (e.work_mode || 'WFO') === 'WFO').length;
    const hybridCount = employees.filter(e => (e.work_mode || 'WFO') === 'HYBRID').length;
    const wfhCount = employees.filter(e => (e.work_mode || 'WFO') === 'WFH').length;
    const clientCount = employees.filter(e => (e.work_mode || 'CLIENT_OFFICE') === 'CLIENT_OFFICE').length;

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

        const buHeadColumn = {
            // key: 'bu_head',
            // label: 'BU Head',
            // sortable: false,
            // render: (_value, row) => {
            //     const bu = employeeBUMap[row.employee_code] || 'N/A';
            //     return (
            //         <span style={{
            //             fontSize: 'var(--font-size-sm)',
            //             color: bu === 'N/A' ? 'var(--color-text-muted)' : 'var(--color-text)'
            //         }}>
            //             {bu}
            //         </span>
            //     );
            // }
        };

        if (workModeTab === 'WFH') {
            return [
                ...baseColumns,
                buHeadColumn,
                { key: 'total_office_hours', label: 'Total Hours', sortable: true },
                {
                    key: 'compliance_percentage',
                    label: 'Compliance',
                    sortable: true,
                    render: () => (
                        <div className="flex items-center gap-3">
                            <div className="progress-bar" style={{ width: '80px' }}>
                                <div className="progress-fill green" style={{ width: '100%' }} />
                            </div>
                            <span className="font-medium">100.0%</span>
                        </div>
                    )
                },
                {
                    key: 'status',
                    label: 'Status',
                    sortable: true,
                    render: () => <StatusBadge status="Compliance" />
                }
            ];
        }

        const requiredDays = workModeTab === 'HYBRID' ? 3 : 5;

        return [
            ...baseColumns,
            buHeadColumn,
            { key: 'total_office_hours', label: 'Total Hours', sortable: true },
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
            { key: 'expected_hours', label: 'Expected Hours', sortable: false },
            {
                key: 'compliance_percentage',
                label: 'Compliance',
                sortable: true,
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
                const colors = { WFO: '#3b82f6', HYBRID: '#8b5cf6', WFH: '#06b6d4', CLIENT_OFFICE: '#f59e0b' };
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
        // {
        //     key: 'bu_head',
        //     label: 'BU Head',
        //     sortable: false,
        //     render: (_value, row) => {
        //         const bu = employeeBUMap[row.employee_code] || 'N/A';
        //         return (
        //             <span style={{
        //                 fontSize: 'var(--font-size-sm)',
        //                 color: bu === 'N/A' ? 'var(--color-text-muted)' : 'var(--color-text)'
        //             }}>
        //                 {bu}
        //             </span>
        //         );
        //     }
        // },
        { key: 'total_office_hours', label: 'Total Hours', sortable: true },
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
        { key: 'expected_hours', label: 'Expected', sortable: false },
        {
            key: 'compliance_percentage',
            label: 'Compliance',
            sortable: true,
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
            sortable: true,
            render: (value) => <StatusBadge status={value} />
        }
    ];

    const columns = workModeTab ? getColumns() : allColumns;

    // Dashboard filter label
    const compHrs = complianceSettings?.compliance_hours ?? 9;
    const dashboardFilterLabels = {
        'non_exempt': 'Non-Exempted Employees (WFO + Hybrid)',
        'compliant': `Compliant to WFO Policy (≥${compHrs}h)`,
        'non_compliant': `Non-Compliant to WFO Policy (<${compHrs}h)`
    };

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <h1 className="page-title">All Employees Report</h1>
                <p className="page-subtitle">
                    View and analyze attendance data for all employees
                </p>
            </div>

            {/* Dashboard Filter Banner */}
            {dashboardFilter && dashboardFilterLabels[dashboardFilter] && (
                <div className="card mb-4" style={{
                    background: 'var(--color-primary-bg, #eff6ff)',
                    borderColor: 'var(--color-primary, #3b82f6)',
                    borderLeft: '4px solid var(--color-primary, #3b82f6)',
                    padding: 'var(--spacing-3) var(--spacing-4)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <span style={{ fontWeight: 600, color: 'var(--color-primary, #3b82f6)' }}>
                        Filtered: {dashboardFilterLabels[dashboardFilter]}
                    </span>
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={clearDashboardFilter}
                        style={{ fontSize: 'var(--font-size-sm)' }}
                    >
                        Clear Filter
                    </button>
                </div>
            )}

            {/* Filters */}
            <div className="card mb-6">
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
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

                    {/* Year Filter */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Year</label>
                        <select
                            className="form-input form-select"
                            value={selectedYear}
                            onChange={(e) => handleYearChange(Number(e.target.value))}
                        >
                            {years.map((y) => (
                                <option key={y} value={y}>{y}</option>
                            ))}
                        </select>
                    </div>

                    {/* Week Filter */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Week</label>
                        <select
                            className="form-input form-select"
                            value={selectedWeekValue}
                            onChange={(e) => setSelectedWeekValue(e.target.value)}
                        >
                            {isoWeeks.map((w) => (
                                <option key={w.value} value={w.value}>
                                    {w.label}
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
                            <option value="Compliance">Compliance</option>
                            <option value="Mid-Compliance">Mid-Compliance</option>
                            <option value="Non-Compliance">Non-Compliance</option>
                        </select>
                    </div>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">BU Head</label>
                        <select
                            className="form-input form-select"
                            value={selectedBUHead}
                            onChange={(e) => setSelectedBUHead(e.target.value)}
                        >
                            <option value="">All BU Heads</option>
                            {buHeads.map((bu) => (
                                <option key={bu} value={bu}>{bu}</option>
                            ))}
                        </select>
                    </div>

                    {/* Export Button */}
                    <div style={{ display: "flex", alignItems: "end" }}>
                        <button
                            className="btn btn-primary"
                            onClick={handleExport}
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "8px",
                                width: "fit-content",
                                whiteSpace: "nowrap",
                                padding: "10px 14px"
                            }}
                        >
                            <Download size={18} />
                            Export CSV
                        </button>
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
                    {avgCompliance}%
                </div>
                <div className="text-muted">Avg Compliance (WFO + Hybrid only)</div>
                </div>

                <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-4)', background: 'var(--color-status-green-bg)', borderColor: 'var(--color-status-green-border)' }}>
                    <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 'bold', color: 'var(--color-status-green)' }}>
                        {filteredEmployees.filter(e => {
                            if (!workModeTab) return (e.work_mode || 'WFO') !== 'WFH' && e.status === 'Compliance';
                            return e.status === 'Compliance';
                        }).length}
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>Compliance (≥{complianceSettings?.compliance_hours ?? 9}h)</div>
                </div>

                <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-4)', background: 'var(--color-status-red-bg)', borderColor: 'var(--color-status-red-border)' }}>
                    <div style={{ fontSize: 'var(--font-size-3xl)', fontWeight: 'bold', color: 'var(--color-status-red)' }}>
                    {filteredEmployees.filter(e => {
                        if (!workModeTab) return (e.work_mode || 'WFO') !== 'WFH' && e.status === 'Non-Compliance';
                        return e.status === 'Non-Compliance';
                    }).length}
                    </div>
                    <div className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>Non-Compliance (&lt;{complianceSettings?.mid_compliance_hours ?? 7}h)</div>
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
                <button
                    className={`tab ${workModeTab === 'Client Office' ? 'active' : ''}`}
                    onClick={() => setWorkModeTab('CLIENT_OFFICE')}
                    style={workModeTab === 'CLIENT_OFFICE' ? { borderColor: '#f59e0b', color: '#f59e0b' } : {}}
                >
                    Client Office ({clientCount})
                </button>
            </div>

            {/* Data Table */}
            <div className="table-container">
                <div className="table-header">
                    <h3 className="table-title">
                        {filteredEmployees.length} Employee{filteredEmployees.length !== 1 ? 's' : ''}
                        {workModeTab && ` (${workModeTab})`}
                    </h3>
                   
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
