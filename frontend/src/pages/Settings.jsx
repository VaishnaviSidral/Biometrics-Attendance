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
                threshold_amber: settings?.thresholds?.amber || 90,
                compliance_hours: settings?.compliance_hours || 9,
                mid_compliance_hours: settings?.mid_compliance_hours || 7,
                non_compliance_hours: settings?.non_compliance_hours || 6
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

    const wfoDays = settings?.wfo_days_per_week || 5;
    const hybridDays = settings?.hybrid_days_per_week || 3;
    const hoursPerDay = settings?.expected_hours_per_day || 9;
    const complianceHrs = settings?.compliance_hours || 9;
    const midComplianceHrs = settings?.mid_compliance_hours || 7;
    const nonComplianceHrs = settings?.non_compliance_hours || 6;

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <h1 className="page-title">Settings</h1>
                <p className="page-subtitle">
                    Configure attendance policies and compliance rules
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
                            value={hoursPerDay}
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
                            value={wfoDays}
                            onChange={(e) => setSettings({
                                ...settings,
                                wfo_days_per_week: parseInt(e.target.value)
                            })}
                            min="1"
                            max="7"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            Required office days for WFO employees
                        </p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Hybrid Days Per Week</label>
                        <input
                            type="number"
                            className="form-input"
                            value={hybridDays}
                            onChange={(e) => setSettings({
                                ...settings,
                                hybrid_days_per_week: parseInt(e.target.value)
                            })}
                            min="1"
                            max="7"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            Required office days for Hybrid employees
                        </p>
                    </div>
                </div>

                {/* Summary */}
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
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>WFO Required</p>
                        <p className="font-bold" style={{ color: '#3b82f6', fontSize: 'var(--font-size-lg)' }}>
                            {wfoDays * hoursPerDay}h/week
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                            {wfoDays} days × {hoursPerDay} hrs
                        </p>
                    </div>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Hybrid Required</p>
                        <p className="font-bold" style={{ color: '#8b5cf6', fontSize: 'var(--font-size-lg)' }}>
                            {hybridDays * hoursPerDay}h/week
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                            {hybridDays} days × {hoursPerDay} hrs
                        </p>
                    </div>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>WFH</p>
                        <p className="font-bold" style={{ color: '#06b6d4', fontSize: 'var(--font-size-lg)' }}>
                            Exempted
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>
                            Not counted in compliance
                        </p>
                    </div>
                </div>
            </div>

            {/* Hour-Based Compliance Thresholds */}
            <div className="card mb-6">
                <h3 className="card-title mb-6">Hour-Based Compliance Thresholds</h3>
                <p style={{
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--color-text-muted)',
                    marginBottom: 'var(--spacing-4)'
                }}>
                    Configure daily hour thresholds to determine employee compliance status.
                    Reports update dynamically when these values change.
                </p>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                    gap: 'var(--spacing-6)'
                }}>
                    <div className="form-group">
                        <label className="form-label" style={{ color: 'var(--color-status-green)' }}>
                            Compliance Hours
                        </label>
                        <input
                            type="number"
                            className="form-input"
                            value={complianceHrs}
                            onChange={(e) => setSettings({
                                ...settings,
                                compliance_hours: parseInt(e.target.value)
                            })}
                            min="1"
                            max="24"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            ≥ {complianceHrs}h → Employee is COMPLIANT
                        </p>
                    </div>

                    <div className="form-group">
                        <label className="form-label" style={{ color: '#f59e0b' }}>
                            Mid-Compliance Hours
                        </label>
                        <input
                            type="number"
                            className="form-input"
                            value={midComplianceHrs}
                            onChange={(e) => setSettings({
                                ...settings,
                                mid_compliance_hours: parseInt(e.target.value)
                            })}
                            min="1"
                            max="24"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            ≥ {midComplianceHrs}h and &lt; {complianceHrs}h → MID-COMPLIANCE
                        </p>
                    </div>

                    <div className="form-group">
                        <label className="form-label" style={{ color: 'var(--color-status-red)' }}>
                            Non-Compliance Hours
                        </label>
                        <input
                            type="number"
                            className="form-input"
                            value={nonComplianceHrs}
                            onChange={(e) => setSettings({
                                ...settings,
                                non_compliance_hours: parseInt(e.target.value)
                            })}
                            min="0"
                            max="24"
                        />
                        <p style={{
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-muted)',
                            marginTop: 'var(--spacing-1)'
                        }}>
                            &lt; {midComplianceHrs}h → Non-Compliance
                        </p>
                    </div>
                </div>

                {/* Summary */}
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
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Compliance</p>
                        <p className="font-bold" style={{ color: 'var(--color-status-green)', fontSize: 'var(--font-size-lg)' }}>
                            ≥ {complianceHrs}h
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>Compliance status</p>
                    </div>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Mid-Compliance</p>
                        <p className="font-bold" style={{ color: '#f59e0b', fontSize: 'var(--font-size-lg)' }}>
                            ≥ {midComplianceHrs}h &amp; &lt; {complianceHrs}h
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>Mid-Compliance status</p>
                    </div>
                    <div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>Non-Compliance</p>
                        <p className="font-bold" style={{ color: 'var(--color-status-red)', fontSize: 'var(--font-size-lg)' }}>
                            &lt; {midComplianceHrs}h
                        </p>
                        <p className="text-muted" style={{ fontSize: 'var(--font-size-xs)' }}>Non-Compliance status</p>
                    </div>
                </div>
            </div>

            {/* Compliance Rules */}
            <div className="card mb-6">
                <h3 className="card-title mb-6">Compliance Rules — Daily Discipline Model</h3>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                    gap: 'var(--spacing-4)'
                }}>
                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: 'var(--color-status-green-bg)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-status-green-border)'
                    }}>
                        <div className="flex items-center gap-2 mb-2">
                            <span style={{
                                width: '12px', height: '12px',
                                background: 'var(--color-status-green)',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">COMPLIANT</span>
                        </div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                            Daily hours ≥ {complianceHrs}h on every working day
                        </p>
                        <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                            Weekly/Monthly: All days must be Compliant
                        </p>
                    </div>

                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: '#fef9c3',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid #fde68a'
                    }}>
                        <div className="flex items-center gap-2 mb-2">
                            <span style={{
                                width: '12px', height: '12px',
                                background: '#f59e0b',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">MID-COMPLIANT</span>
                        </div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                            Daily hours ≥ {midComplianceHrs}h and &lt; {complianceHrs}h
                        </p>
                        <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                            Weekly/Monthly: If any Mid-Compliance day exists (and no Non-Compliance)
                        </p>
                    </div>

                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: 'var(--color-status-red-bg)',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid var(--color-status-red-border)'
                    }}>
                        <div className="flex items-center gap-2 mb-2">
                            <span style={{
                                width: '12px', height: '12px',
                                background: 'var(--color-status-red)',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">NON-COMPLIANT</span>
                        </div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                            Daily hours &lt; {midComplianceHrs}h or Absent
                        </p>
                        <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                            Weekly/Monthly: If any Non-Compliance day exists
                        </p>
                    </div>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr',
                    gap: 'var(--spacing-3)',
                    marginTop: 'var(--spacing-4)'
                }}>
                    <div style={{
                        padding: 'var(--spacing-4)',
                        background: '#dbeafe',
                        borderRadius: 'var(--radius-lg)',
                        border: '1px solid #93c5fd'
                    }}>
                        <div className="flex items-center gap-2 mb-2">
                            <span style={{
                                width: '12px', height: '12px',
                                background: '#2563eb',
                                borderRadius: 'var(--radius-full)'
                            }}></span>
                            <span className="font-medium">EXEMPTED (WFH)</span>
                        </div>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
                            WFH employees — always marked as Compliant
                        </p>
                    </div>
                </div>

                {/* Attendance note */}
                <div style={{
                    marginTop: 'var(--spacing-4)',
                    padding: 'var(--spacing-3)',
                    background: 'var(--color-surface-elevated)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--color-text-muted)'
                }}>
                    <strong>Daily Discipline Rule:</strong> Compliance is evaluated per day using configured expected hours.
                    Weekly and monthly compliance are aggregations of daily compliance statuses — not aggregations of hours.
                    Working extra on some days does <strong>NOT</strong> compensate for underworking on other days.
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
                    Reset
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
