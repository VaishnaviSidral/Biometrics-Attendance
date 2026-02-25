import { useState, useEffect } from 'react';
import { Search, Plus, Edit2, X } from 'lucide-react';
import api from '../api/client';

const WORK_MODE_OPTIONS = ['WFO', 'HYBRID', 'WFH', 'CLIENT_OFFICE'];

const WORK_MODE_COLORS = {
    WFO: '#3b82f6',
    HYBRID: '#8b5cf6',
    WFH: '#06b6d4',
    CLIENT_OFFICE: '#f59e0b'
};

const emptyEmployee = {
    code: '',
    name: '',
    email: '',
    department: '',
    work_mode: 'WFO',
    status: 1
};

export default function ManageEmployees() {
    const [employees, setEmployees] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [modalOpen, setModalOpen] = useState(false);
    const [modalMode, setModalMode] = useState('add'); // 'add' | 'edit'
    const [formData, setFormData] = useState({ ...emptyEmployee });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');

    useEffect(() => {
        fetchEmployees();
    }, []);

    const fetchEmployees = async () => {
        try {
            setLoading(true);
            const data = await api.getEmployees({ include_inactive: true, limit: 1000 });
            setEmployees(data.employees || []);
        } catch (err) {
            console.error('Error fetching employees:', err);
        } finally {
            setLoading(false);
        }
    };

    // Open modal for adding a new employee
    const handleAdd = () => {
        setFormData({ ...emptyEmployee });
        setModalMode('add');
        setError('');
        setModalOpen(true);
    };

    // Open modal for editing an existing employee
    const handleEdit = (emp) => {
        setFormData({
            code: emp.code,
            name: emp.name,
            email: emp.email || '',
            department: emp.department || '',
            work_mode: emp.work_mode || 'WFO',
            status: emp.status !== undefined ? emp.status : 1
        });
        setModalMode('edit');
        setError('');
        setModalOpen(true);
    };

    const handleCloseModal = () => {
        setModalOpen(false);
        setError('');
    };

    const handleFormChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSave = async () => {
        // Validation
        if (!formData.code.trim()) {
            setError('Employee code is required');
            return;
        }
        // Numeric-only validation
        if (!/^\d+$/.test(formData.code.trim())) {
            setError('Employee code must contain only numbers');
            return;
        }
        if (!formData.name.trim()) {
            setError('Employee name is required');
            return;
        }
        if (!formData.email.trim()) {
            setError('Employee email is required');
            return;
        }
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(formData.email.trim())) {
            setError('Please enter a valid email address');
            return;
        }

        try {
            setSaving(true);
            setError('');

            if (modalMode === 'add') {
                await api.createEmployee({
                    code: formData.code.trim(),
                    name: formData.name.trim(),
                    email: formData.email.trim() || null,
                    department: formData.department.trim() || null,
                    work_mode: formData.work_mode,
                    status: formData.status
                });
                setSuccessMsg('Employee added successfully');
            } else {
                await api.updateEmployee(formData.code, {
                    name: formData.name.trim(),
                    email: formData.email.trim() || null,
                    department: formData.department.trim() || null,
                    work_mode: formData.work_mode,
                    status: formData.status
                });
                setSuccessMsg('Employee updated successfully');
            }

            setModalOpen(false);
            await fetchEmployees();
            setTimeout(() => setSuccessMsg(''), 3000);
        } catch (err) {
            setError(err.message || 'Failed to save employee');
        } finally {
            setSaving(false);
        }
    };

    // Filter employees by search
    const filteredEmployees = employees.filter(emp => {
        if (!searchTerm) return true;
        const term = searchTerm.toLowerCase();
        return (
            emp.name?.toLowerCase().includes(term) ||
            emp.code?.toLowerCase().includes(term) ||
            emp.email?.toLowerCase().includes(term) ||
            emp.department?.toLowerCase().includes(term)
        );
    });

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <div className="flex justify-between items-center" style={{ width: '100%' }}>
                    <div>
                        <h1 className="page-title">Manage Employees</h1>
                        <p className="page-subtitle">
                            Add, edit, or deactivate employee records
                        </p>
                    </div>
                    <button className="btn btn-primary" onClick={handleAdd}>
                        <Plus size={18} />
                        Add Employee
                    </button>
                </div>
            </div>

            {/* Success Message */}
            {successMsg && (
                <div style={{
                    padding: 'var(--spacing-3) var(--spacing-4)',
                    background: 'var(--color-status-green-bg)',
                    border: '1px solid var(--color-status-green-border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--color-status-green)',
                    marginBottom: 'var(--spacing-4)',
                    fontWeight: 600
                }}>
                    ✓ {successMsg}
                </div>
            )}

            {/* Search */}
            <div className="card mb-6">
                <div className="form-group" style={{ marginBottom: 0 }}>
                    <div style={{ position: 'relative', maxWidth: '400px' }}>
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
                            placeholder="Search by name, code, email, or department..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            style={{ paddingLeft: '40px' }}
                        />
                    </div>
                </div>
            </div>

            {/* Employees Table */}
            <div className="table-container">
                <div className="table-header">
                    <h3 className="table-title">
                        {filteredEmployees.length} Employee{filteredEmployees.length !== 1 ? 's' : ''}
                    </h3>
                </div>
                <div className="table-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Employee</th>
                                <th>Email</th>
                                {/* <th>Department</th> */}
                                <th>Work Mode</th>
                                <th>Status</th>
                                <th style={{ textAlign: 'center' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={6} style={{ textAlign: 'center', padding: '24px' }}>
                                        <div className="loading-spinner" style={{ margin: '0 auto' }}></div>
                                    </td>
                                </tr>
                            ) : filteredEmployees.length === 0 ? (
                                <tr>
                                    <td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: 'var(--color-text-muted)' }}>
                                        No employees found.
                                    </td>
                                </tr>
                            ) : (
                                filteredEmployees.map((emp) => (
                                    <tr key={emp.code}>
                                        {/* Employee */}
                                        <td>
                                            <div className="cell-employee">
                                                <div className="employee-avatar">
                                                    {emp.name?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                                                </div>
                                                <div className="employee-info">
                                                    <span className="employee-name">{emp.name}</span>
                                                    <span className="employee-code">ID: {emp.code}</span>
                                                </div>
                                            </div>
                                        </td>

                                        {/* Email */}
                                        <td>
                                            <span style={{ fontSize: 'var(--font-size-sm)' }}>
                                                {emp.email || '-'}
                                            </span>
                                        </td>

                                        {/* Department */}
                                        {/* <td>
                                            <span style={{ fontSize: 'var(--font-size-sm)' }}>
                                                {emp.department || '-'}
                                            </span>
                                        </td> */}

                                        {/* Work Mode */}
                                        <td>
                                            <span style={{
                                                padding: '2px 8px',
                                                borderRadius: '4px',
                                                fontSize: 'var(--font-size-xs)',
                                                fontWeight: 600,
                                                background: `${WORK_MODE_COLORS[emp.work_mode] || WORK_MODE_COLORS.WFO}20`,
                                                color: WORK_MODE_COLORS[emp.work_mode] || WORK_MODE_COLORS.WFO
                                            }}>
                                                {emp.work_mode || 'WFO'}
                                            </span>
                                        </td>

                                        {/* Status */}
                                        <td>
                                            <span style={{
                                                padding: '2px 10px',
                                                borderRadius: '999px',
                                                fontSize: 'var(--font-size-xs)',
                                                fontWeight: 600,
                                                background: emp.status === 1 ? '#10b98120' : '#ef444420',
                                                color: emp.status === 1 ? '#10b981' : '#ef4444'
                                            }}>
                                                {emp.status === 1 ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>

                                        {/* Actions */}
                                        <td style={{ textAlign: 'center' }}>
                                            <button
                                                className="btn btn-secondary btn-sm"
                                                onClick={() => handleEdit(emp)}
                                                style={{
                                                    padding: '6px 12px',
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '4px'
                                                }}
                                            >
                                                <Edit2 size={14} />
                                                Edit
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Add/Edit Modal */}
            {modalOpen && (
                <div className="modal-overlay" style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <div className="modal-content" style={{
                        background: 'var(--color-surface)',
                        borderRadius: 'var(--radius-lg)',
                        width: '90%', maxWidth: '550px',
                        boxShadow: 'var(--shadow-xl)'
                    }}>
                        {/* Modal Header */}
                        <div style={{
                            padding: 'var(--spacing-4) var(--spacing-6)',
                            borderBottom: '1px solid var(--color-border)',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}>
                            <h3 className="font-bold" style={{ fontSize: 'var(--font-size-lg)' }}>
                                {modalMode === 'add' ? 'Add New Employee' : 'Edit Employee'}
                            </h3>
                            <button
                                onClick={handleCloseModal}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
                            >
                                <X size={24} />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div style={{ padding: 'var(--spacing-6)' }}>
                            {error && (
                                <div style={{
                                    padding: 'var(--spacing-3)',
                                    background: 'var(--color-status-red-bg)',
                                    border: '1px solid var(--color-status-red-border)',
                                    borderRadius: 'var(--radius-md)',
                                    color: 'var(--color-status-red)',
                                    marginBottom: 'var(--spacing-4)',
                                    fontSize: 'var(--font-size-sm)'
                                }}>
                                    {error}
                                </div>
                            )}

                            <div style={{ display: 'grid', gap: 'var(--spacing-4)' }}>
                                {/* Employee Code */}
                                <div className="form-group" style={{ marginBottom: 0 }}>
                                    <label className="form-label">Employee Code *</label>
                                    <input
                                        type="text"
                                        className="form-input"
                                        value={formData.code}
                                        onChange={(e) => handleFormChange('code', e.target.value)}
                                        disabled={modalMode === 'edit'}
                                        placeholder="e.g. EMP001"
                                        style={modalMode === 'edit' ? { opacity: 0.6, cursor: 'not-allowed' } : {}}
                                    />
                                </div>

                                {/* Employee Name */}
                                <div className="form-group" style={{ marginBottom: 0 }}>
                                    <label className="form-label">Full Name *</label>
                                    <input
                                        type="text"
                                        className="form-input"
                                        value={formData.name}
                                        onChange={(e) => handleFormChange('name', e.target.value)}
                                        placeholder="e.g. John Doe"
                                    />
                                </div>

                                {/* Email */}
                                <div className="form-group" style={{ marginBottom: 0 }}>
                                    <label className="form-label">Email *</label>
                                    <input
                                        type="email"
                                        className="form-input"
                                        value={formData.email}
                                        onChange={(e) => handleFormChange('email', e.target.value)}
                                        placeholder="e.g. john@company.com"
                                    />
                                </div>

                                {/* Department */}
                                {/* <div className="form-group" style={{ marginBottom: 0 }}>
                                    <label className="form-label">Department</label>
                                    <input
                                        type="text"
                                        className="form-input"
                                        value={formData.department}
                                        onChange={(e) => handleFormChange('department', e.target.value)}
                                        placeholder="e.g. Engineering"
                                    />
                                </div> */}

                                {/* Work Mode + Status row */}
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
                                    {/* Work Mode */}
                                    <div className="form-group" style={{ marginBottom: 0 }}>
                                        <label className="form-label">Work Mode</label>
                                        <select
                                            className="form-input form-select"
                                            value={formData.work_mode}
                                            onChange={(e) => handleFormChange('work_mode', e.target.value)}
                                        >
                                            {WORK_MODE_OPTIONS.map(mode => (
                                                <option key={mode} value={mode}>{mode}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Status */}
                                    <div className="form-group" style={{ marginBottom: 0 }}>
                                        <label className="form-label">Status</label>
                                        <select
                                            className="form-input form-select"
                                            value={formData.status}
                                            onChange={(e) => handleFormChange('status', parseInt(e.target.value))}
                                        >
                                            <option value={1}>Active</option>
                                            <option value={0}>Inactive</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div style={{
                            padding: 'var(--spacing-4) var(--spacing-6)',
                            borderTop: '1px solid var(--color-border)',
                            display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-3)'
                        }}>
                            <button
                                className="btn btn-secondary"
                                onClick={handleCloseModal}
                                disabled={saving}
                            >
                                Cancel
                            </button>
                            <button
                                className="btn btn-primary"
                                onClick={handleSave}
                                disabled={saving}
                            >
                                {saving ? 'Saving...' : (modalMode === 'add' ? 'Add Employee' : 'Update Employee')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

