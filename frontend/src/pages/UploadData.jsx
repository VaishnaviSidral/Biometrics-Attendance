import { useState } from 'react';
import { Upload, FileSpreadsheet, Info } from 'lucide-react';
import api from '../api/client';
import FileUpload from '../components/FileUpload';

export default function UploadData() {
    const [isLoading, setIsLoading] = useState(false);

    const handleUpload = async (file) => {
        setIsLoading(true);
        try {
            const result = await api.uploadFile(file);
            return result;
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="animate-fade-in">
            {/* Page Header */}
            <div className="page-header">
                <h1 className="page-title">Upload Attendance Data</h1>
                <p className="page-subtitle">
                    Import biometric attendance logs from your fingerprint system
                </p>
            </div>

            {/* Instructions */}
            <div className="card mb-6" style={{
                background: 'var(--color-primary-light)',
                borderColor: 'var(--color-primary)'
            }}>
                <div className="flex items-center gap-3 mb-4">
                    <Info size={24} style={{ color: 'var(--color-primary)' }} />
                    <h3 style={{ color: 'var(--color-primary)' }}>File Format Requirements</h3>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 'var(--spacing-4)'
                }}>
                    <div>
                        <p className="font-medium mb-2">Required Columns:</p>
                        <ul style={{
                            listStyle: 'none',
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--color-text-secondary)'
                        }}>
                            <li>• DATE (DD/MM/YYYY)</li>
                            <li>• CODE (Employee ID)</li>
                            <li>• NAME (Employee Name)</li>
                            <li>• IN (Clock-in time)</li>
                            <li>• OUT (Clock-out time)</li>
                        </ul>
                    </div>

                    <div>
                        <p className="font-medium mb-2">Optional Columns:</p>
                        <ul style={{
                            listStyle: 'none',
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--color-text-secondary)'
                        }}>
                            <li>• TOTAL (Total hours)</li>
                            <li>• SHIFT</li>
                            <li>• LATE</li>
                            <li>• OT (Overtime)</li>
                            <li>• REMARK</li>
                        </ul>
                    </div>

                    <div>
                        <p className="font-medium mb-2">Supported Formats:</p>
                        <ul style={{
                            listStyle: 'none',
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--color-text-secondary)'
                        }}>
                            <li>• CSV (.csv)</li>
                            <li>• Excel (.xlsx)</li>
                            <li>• Legacy Excel (.xls)</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* File Upload */}
            <FileUpload onUpload={handleUpload} isLoading={isLoading} />

            {/* Sample Data Preview */}
            <div className="card mt-6">
                <div className="card-header">
                    <h3 className="card-title">Expected Data Format</h3>
                </div>

                <div className="table-wrapper" style={{ marginTop: 'var(--spacing-4)' }}>
                    <table>
                        <thead>
                            <tr>
                                <th>DATE</th>
                                <th>CODE</th>
                                <th>NAME</th>
                                <th>IN</th>
                                <th>OUT</th>
                                <th>TOTAL</th>
                                <th>REMARK</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>01/12/2025</td>
                                <td>101</td>
                                <td>John Doe</td>
                                <td>09:44</td>
                                <td>14:02</td>
                                <td>04:18:00</td>
                                <td>P</td>
                            </tr>
                            <tr>
                                <td>01/12/2025</td>
                                <td>102</td>
                                <td>Jane Smith</td>
                                <td>10:19</td>
                                <td>14:20</td>
                                <td>04:01:00</td>
                                <td>P</td>
                            </tr>
                            <tr>
                                <td>01/12/2025</td>
                                <td>103</td>
                                <td>Robert Brown</td>
                                <td>13:00</td>
                                <td>09:06</td>
                                <td>02:54:00</td>
                                <td>P</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <p style={{
                    marginTop: 'var(--spacing-4)',
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--color-text-muted)'
                }}>
                    This is sample data showing the expected format from your biometric system export.
                </p>
            </div>
        </div>
    );
}
