import { useEffect, useState } from "react";
import { Download, Search, Calendar } from "lucide-react";
import api from "../api/client";

export default function MonthlyReport({ workMode }) {
    const [month, setMonth] = useState("");
    const [searchTerm, setSearchTerm] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);

    // Default to current month
    useEffect(() => {
        const now = new Date();
        const m = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
        setMonth(m);
    }, []);

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchTerm);
        }, 400);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    useEffect(() => {
        if (month) {
            fetchData();
        }
    }, [month, debouncedSearch, workMode]);

    const fetchData = async () => {
        try {
            setLoading(true);
            const params = { month, search: debouncedSearch };
            if (workMode) params.work_mode = workMode;
            const res = await api.getMonthlyReport(params);
            setData(res || []);
        } catch (err) {
            console.error("Error fetching monthly report:", err);
        } finally {
            setLoading(false);
        }
    };
    const handleExportCSV = async () => {
        try {
            if (!month) return;

            // month = "2026-02"
            const [year, m] = month.split("-");
            const monthName = new Date(month + "-01").toLocaleDateString("en-US", { month: "long" }).toLowerCase();

            const filename = `monthly_report_${monthName}_${year}.csv`;

            await api.exportMonthlyReportCSV(
                { month, search: debouncedSearch, work_mode: workMode },
                filename
            );
        } catch (err) {
            console.error("Monthly export error:", err);
        }
    };


    const handleIndividualExport = async (employeeCode) => {
        try {
            await api.exportMonthlyIndividual(employeeCode, month);
        } catch (err) {
            console.error("Export error:", err);
        }
    };

    // Summary counts
    const totalEmployees = data.length;
    const exemptedCount = data.filter((e) => e.exempted).length;
    const nonExemptedCount = totalEmployees - exemptedCount;
    const workingDays = data.length > 0 ? data[0].working_days || 0 : 0;

    // Month label
    const monthLabel = month
        ? new Date(month + "-01").toLocaleDateString("en-US", { month: "long", year: "numeric" })
        : "";

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <h1 className="page-title">{workMode ? `${workMode} Monthly Attendance Report` : 'Monthly Attendance Report'}</h1>
                <p className="page-subtitle">
                    {monthLabel
                        ? `${monthLabel} — ${workingDays} working days`
                        : "Monthly MIS report for management"}
                </p>
            </div>

            {/* Filters */}
            <div className="card mb-6">
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                        gap: "var(--spacing-4)",
                        alignItems: "end",
                    }}
                >
                    {/* Month Filter */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Month</label>
                        <input
                            type="month"
                            className="form-input"
                            value={month}
                            onChange={(e) => setMonth(e.target.value)}
                        />
                    </div>

                    {/* Employee Search */}
                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label">Search Employee</label>
                        <div style={{ position: "relative" }}>
                            <Search
                                size={18}
                                style={{
                                    position: "absolute",
                                    left: "12px",
                                    top: "50%",
                                    transform: "translateY(-50%)",
                                    color: "var(--color-text-muted)",
                                    pointerEvents: "none",
                                }}
                            />
                            <input
                                type="text"
                                className="form-input"
                                placeholder="Search by name or ID..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                style={{ paddingLeft: "40px" }}
                            />
                        </div>
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={handleExportCSV}
                        disabled={!month || loading}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "8px",
                            width: "fit-content",
                            justifySelf: "start",   // 👈 prevents full column stretch
                            padding: "12px 13px"    // 👈 tighter button
                        }}
                    >
                        <Download size={18} />
                        Export CSV
                    </button>

                </div>
            </div>

            {/* Data Table */}
            <div className="table-container">
                <div className="table-header">
                    <h3 className="table-title">
                        {data.length} Employee{data.length !== 1 ? "s" : ""}
                    </h3>
                </div>

                <div className="table-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Employee</th>
                                <th>Mode</th>
                                <th>Exempted</th>
                                {/* <th>WFO Days</th>
                                <th>WFH Days</th> */}
                                <th>Compliance</th>
                                <th>Status</th>
                            </tr>
                        </thead>

                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={7} style={{ textAlign: "center", padding: "20px" }}>
                                        Loading...
                                    </td>
                                </tr>
                            ) : data.length === 0 ? (
                                <tr>
                                    <td colSpan={7} style={{ textAlign: "center", padding: "20px" }}>
                                        No data found for this month. Try adjusting your filters or upload attendance data.
                                    </td>
                                </tr>
                            ) : (
                                data.map((row, index) => {
                                    const mode = row.work_mode || "WFO";
                                    const modeColors = { WFO: "#3b82f6", HYBRID: "#8b5cf6", WFH: "#06b6d4" };

                                    const compliance = row.compliance_percentage || 0;
                                    let statusClass = "green";
                                    if (compliance < 60) statusClass = "red";
                                    else if (compliance < 90) statusClass = "amber";

                                    const status = row.compliance_status || "Non-Compliance";
                                    const statusColors = {
                                        Compliance: "#16a34a",
                                        "Mid-Compliance": "#f59e0b",
                                        "Non-Compliance": "#dc2626",
                                    };

                                    return (
                                        <tr key={row.employee_code || index}>
                                            {/* Employee */}
                                            <td>
                                                <div className="cell-employee">
                                                    <div className="employee-avatar">
                                                        {row.employee_name
                                                            ?.split(" ")
                                                            .map((n) => n[0])
                                                            .join("")
                                                            .slice(0, 2)
                                                            .toUpperCase()}
                                                    </div>
                                                    <div className="employee-info">
                                                        <span className="employee-name">{row.employee_name}</span>
                                                        <span className="employee-code">ID: {row.employee_code}</span>
                                                    </div>
                                                </div>
                                            </td>

                                            {/* Mode */}
                                            <td>
                                                <span
                                                    style={{
                                                        padding: "2px 8px",
                                                        borderRadius: "4px",
                                                        fontSize: "var(--font-size-xs)",
                                                        fontWeight: 600,
                                                        background: `${modeColors[mode] || modeColors.WFO}20`,
                                                        color: modeColors[mode] || modeColors.WFO,
                                                    }}
                                                >
                                                    {mode}
                                                </span>
                                            </td>

                                            {/* Exempted */}
                                            <td>
                                                <span
                                                    style={{
                                                        padding: "2px 8px",
                                                        borderRadius: "4px",
                                                        fontSize: "var(--font-size-xs)",
                                                        fontWeight: 600,
                                                        background: row.exempted ? "#06b6d420" : "#6b728020",
                                                        color: row.exempted ? "#06b6d4" : "#6b7280",
                                                    }}
                                                >
                                                    {row.exempted ? "YES" : "NO"}
                                                </span>
                                            </td>

                                            {/* WFO Days */}
                                            {/* <td>
                                                <span>
                                                    <span className="font-medium">{row.total_wfo_days}</span>
                                                    <span className="text-muted">
                                                        {" "}
                                                        / {row.required_days || row.working_days}
                                                    </span>
                                                </span>
                                            </td> */}

                                            {/* WFH Days */}
                                            {/* <td>{row.total_wfh_days}</td> */}

                                            {/* Compliance */}
                                            <td>
                                                <div className="flex items-center gap-3">
                                                    <div className="progress-bar" style={{ width: "80px" }}>
                                                        <div
                                                            className={`progress-fill ${statusClass}`}
                                                            style={{ width: `${Math.min(compliance, 100)}%` }}
                                                        />
                                                    </div>
                                                    <span className="font-medium">{compliance.toFixed(1)}%</span>
                                                </div>
                                            </td>

                                            {/* Status */}
                                            <td>
                                                <span
                                                    style={{
                                                        padding: "4px 10px",
                                                        borderRadius: "999px",
                                                        fontSize: "12px",
                                                        fontWeight: 600,
                                                        background: `${statusColors[status] || "#dc2626"}20`,
                                                        color: statusColors[status] || "#dc2626",
                                                    }}
                                                >
                                                    {status}
                                                </span>
                                            </td>

                                            {/* Individual Export Button (kept but commented like original) */}
                                            {/*
                                            <td>
                                                <button
                                                    className="btn btn-secondary btn-sm"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleIndividualExport(row.employee_code);
                                                    }}
                                                    title="Download monthly report"
                                                    style={{ padding: "4px 8px", display: "flex", alignItems: "center", gap: "4px" }}
                                                >
                                                    <Download size={14} />
                                                </button>
                                            </td>
                                            */}
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
