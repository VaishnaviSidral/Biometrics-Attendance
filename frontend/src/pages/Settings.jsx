import { useState, useEffect } from 'react';
import { Save, RefreshCw } from 'lucide-react';
import api from '../api/client';

export default function Settings() {
    const [settings, setSettings] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        fetchSettings();
    }, []);

    const fetchSettings = async () => {
        try {
            const data = await api.getSettings();
            setSettings(data);
        } catch (err) {
            console.error('Error fetching settings:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        try {
            await api.updateSettings({
                expected_hours_per_day: settings?.expected_hours_per_day || 9,
                wfo_days_per_week: settings?.wfo_days_per_week || 5,
                hybrid_days_per_week: settings?.hybrid_days_per_week || 3,
                threshold_red: settings?.thresholds?.red || 60,
                threshold_amber: settings?.thresholds?.amber || 90
            });
            setSaved(true);
            setTimeout(() => setSaved(false), 3000);
        } catch (err) {
            console.error('Error saving settings:', err);
            alert('Failed to save settings. Please try again.');
        }
    };

    if (loading) {
        return (
            <div className="loading-overlay">
                <div className="loading-spinner"></div>
            </div>
        );
    }

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <h1 className="page-title">Settings</h1>
                <p className="page-subtitle">
                    Configure attendance policies and compliance thresholds
                </p>
            </div>

            {/* Work Mode Policy */}
            <div className="card mb-6">
                <h3 className="card-title mb-6">Work Mode Policies</h3>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                    gap: 'var(--spacing-6)'
                }}>
                    <div className="form-group">
                        <label className="form-label">Expected Hours Per Day</label>
                        <input
                            type="number"
                            className="form-input"
                            value={settings?.expected_hours_per_day || 9}
                            onChange={(e) => setSettings({
                                ...settings,
                                expected_hours_per_day: parseInt(e.target.value)
                            })}
                            min="1"
                            max="12"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            Standard working hours expected per office day
                        </p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">WFO Days Per Week</label>
                        <input
                            type="number"
                            className="form-input"
                            value={settings?.wfo_days_per_week || 5}
                            onChange={(e) => setSettings({
                                ...settings,
                                wfo_days_per_week: parseInt(e.target.value)
                            })}
                            min="1"
                            max="5"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            Required office days for WFO employees (default 5)
                        </p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Hybrid Days Per Week</label>
                        <input
                            type="number"
                            className="form-input"
                            value={settings?.hybrid_days_per_week || 3}
                            onChange={(e) => setSettings({
                                ...settings,
                                hybrid_days_per_week: parseInt(e.target.value)
                            })}
                            min="1"
                            max="5"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            Required office days for Hybrid employees (default 3)
                        </p>
                    </div>
                </div>

                {/* Work Mode Expected Hours Summary */}
                <div style={{
                    marginTop: 'var(--spacing-6)',
                    padding: 'var(--spacing-4)',
                    background: 'var(--color-surface-elevated)',
                    borderRadius: 'var(--radius-lg)',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 'var(--spacing-4)'
                }}>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>WFO Expected</p>
                        <p className="font-bold" style={{ color: '#3b82f6', fontSize: 'var(--font-size-lg)' }}>
                            {(settings?.wfo_days_per_week || 5) * (settings?.expected_hours_per_day || 9)}h/week
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                            {settings?.wfo_days_per_week || 5} days × {settings?.expected_hours_per_day || 9} hrs
                        </p>
                    </div>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Hybrid Expected</p>
                        <p className="font-bold" style={{ color: '#8b5cf6', fontSize: 'var(--font-size-lg)' }}>
                            {(settings?.hybrid_days_per_week || 3) * (settings?.expected_hours_per_day || 9)}h/week
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                            {settings?.hybrid_days_per_week || 3} days × {settings?.expected_hours_per_day || 9} hrs
                        </p>
                    </div>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>WFH Expected</p>
                        <p className="font-bold" style={{ color: '#06b6d4', fontSize: 'var(--font-size-lg)' }}>
                            Tracking Only
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                            Always 100% compliant
                        </p>
                    </div>
                </div>

                {/* Note: PRESENT threshold uses Expected Hours Per Day above */}
                <div style={{ marginTop: 'var(--spacing-4)' }}>
                    <p style={{
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--color-text-muted)',
                        fontStyle: 'italic'
                    }}>
                        Note: An employee is marked as PRESENT for a day only if they work at least the Expected Hours Per Day configured above.
                    </p>
                </div>
            </div>

            {/* Compliance Thresholds */}
            <div className="card mb-6">
                <h3 className="card-title mb-6">Compliance Thresholds</h3>

                <p className="text-muted mb-4" style={{ fontSize: 'var(--font-size-sm)' }}>
                    Set the percentage thresholds that determine employee compliance status
                </p>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                    gap: 'var(--spacing-6)'
                }}>
                    {/* Non-Compliance (RED) */}
                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: 'var(--color-status-red-bg)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-status-red-border)'
                    }}>
                        <div className="flex items-center gap-2 mb-3">
                            <span style={{
                                width: '12px',
                                height: '12px',
                                background: 'var(--color-status-red)',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">Non-Compliance</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span>&lt;</span>
                            <input
                                type="number"
                                className="form-input"
                                value={settings?.thresholds?.red || 60}
                                onChange={(e) => setSettings({
                                    ...settings,
                                    thresholds: {
                                        ...settings?.thresholds,
                                        red: parseInt(e.target.value)
                                    }
                                })}
                                min="0"
                                max="100"
                                style={{ width: '80px', textAlign: 'center' }}
                            />
                            <span>%</span>
                        </div>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--spacing-2)' }}>
                            Employees below this need improvement
                        </p>
                    </div>

                    {/* Mid-Compliance (AMBER) */}
                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: 'var(--color-status-amber-bg)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-status-amber-border)'
                    }}>
                        <div className="flex items-center gap-2 mb-3">
                            <span style={{
                                width: '12px',
                                height: '12px',
                                background: 'var(--color-status-amber)',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">Mid-Compliance</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span>{settings?.thresholds?.red || 60}% –</span>
                            <input
                                type="number"
                                className="form-input"
                                value={settings?.thresholds?.amber || 90}
                                onChange={(e) => setSettings({
                                    ...settings,
                                    thresholds: {
                                        ...settings?.thresholds,
                                        amber: parseInt(e.target.value)
                                    }
                                })}
                                min="0"
                                max="100"
                                style={{ width: '80px', textAlign: 'center' }}
                            />
                            <span>%</span>
                        </div>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--spacing-2)' }}>
                            Satisfactory performance range
                        </p>
                    </div>

                    {/* Compliance (GREEN) */}
                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: 'var(--color-status-green-bg)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-status-green-border)'
                    }}>
                        <div className="flex items-center gap-2 mb-3">
                            <span style={{
                                width: '12px',
                                height: '12px',
                                background: 'var(--color-status-green)',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">Compliance</span>
                        </div>
                        <p className="text-green font-bold" style={{ fontSize: 'var(--font-size-xl)' }}>
                            &ge; {settings?.thresholds?.amber || 90}%
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)', marginTop: 'var(--spacing-2)' }}>
                            Outstanding compliance
                        </p>
                    </div>
                </div>
            </div>

            {/* Save Button */}
            <div className="flex items-center gap-4">
                <button className="btn btn-primary" onClick={handleSave}>
                    <Save size={18} />
                    Save Settings
                </button>

                <button className="btn btn-secondary" onClick={fetchSettings}>
                    <RefreshCw size={18} />
                    Reset to Defaults
                </button>

                {saved && (
                    <span className="text-green" style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--spacing-2)'
                    }}>
                        ✓ Settings saved successfully
                    </span>
                )}
            </div>
        </div>
    );
}
