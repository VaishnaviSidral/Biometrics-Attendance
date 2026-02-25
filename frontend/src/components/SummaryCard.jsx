export default function SummaryCard({
    icon: Icon,
    value,
    label,
    trend,
    trendDirection,
    status,
    description,
    onClick
}) {
    const statusClass = status ? status.toLowerCase() : '';
    const clickableStyle = onClick ? { cursor: 'pointer' } : {};

    return (
        <div
            className={`summary-card ${statusClass} animate-slide-up`}
            onClick={onClick}
            style={clickableStyle}
        >
            <div className={`summary-card-icon`}>
                <Icon size={24} />
            </div>
            <div className="summary-card-value">{value}</div>
            <div className="summary-card-label">{label}</div>
            {description && (
                <div className="text-sm text-muted mt-1" style={{ fontSize: '0.75rem', opacity: 0.8 }}>
                    {description}
                </div>
            )}
            {trend && (
                <div className={`summary-card-trend ${trendDirection === 'up' ? 'trend-up' : 'trend-down'}`}>
                    {trendDirection === 'up' ? '↑' : '↓'} {trend}
                </div>
            )}
        </div>
    );
}
