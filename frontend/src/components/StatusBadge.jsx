/**
 * StatusBadge – display-only component.
 * Receives a status string from the API ("Compliance", "Mid-Compliance", "Non-Compliance")
 * and maps it to the appropriate visual color.  No business logic here.
 */
export default function StatusBadge({ status }) {

    const statusMap = {
        "Compliance":      { label: "Compliance",      color: "#16a34a" },
        "Mid-Compliance":  { label: "Mid-Compliance",  color: "#f59e0b" },
        "Non-Compliance":  { label: "Non-Compliance",  color: "#dc2626" },
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

/**
 * Utility: map a status string to a CSS color class name (green/amber/red).
 * Use this wherever you need a CSS class from a status value.
 */
export function statusToCssClass(status) {
    const map = {
        "Compliance":     "green",
        "Mid-Compliance": "amber",
        "Non-Compliance": "red",
    };
    return map[status] || "red";
}
