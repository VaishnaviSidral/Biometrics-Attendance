export default function StatusBadge({ status }) {

    const statusMap = {
        GREEN: { label: "Compliance", color: "#16a34a" },
        AMBER: { label: "Mid-Compliance", color: "#f59e0b" },
        RED:   { label: "Non-Compliance", color: "#dc2626" },
    };

    const config = statusMap[status] || {
        label: status || "Unknown",
        color: "#6b7280"
    };

    return (
        <span
            style={{
                padding: "4px 10px",
                borderRadius: "999px",
                fontSize: "12px",
                fontWeight: 600,
                background: `${config.color}20`,
                color: config.color,
                display: "inline-block",
            }}
        >
            {config.label}
        </span>
    );
}
