import { useState, useRef } from 'react';
import { Upload, FileSpreadsheet, Check, AlertCircle } from 'lucide-react';

export default function FileUpload({ onUpload, isLoading }) {
    const [dragOver, setDragOver] = useState(false);
    const [file, setFile] = useState(null);
    const [uploadStatus, setUploadStatus] = useState(null);
    const fileInputRef = useRef(null);

    const handleDragOver = (e) => {
        e.preventDefault();
        setDragOver(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setDragOver(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragOver(false);

        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile && isValidFile(droppedFile)) {
            setFile(droppedFile);
            setUploadStatus(null);
        }
    };

    const handleFileSelect = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile && isValidFile(selectedFile)) {
            setFile(selectedFile);
            setUploadStatus(null);
        }
    };

    const isValidFile = (file) => {
        const validTypes = [
            'text/csv',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'
        ];
        const validExtensions = ['.csv', '.xlsx', '.xls'];

        const extension = '.' + file.name.split('.').pop().toLowerCase();
        return validTypes.includes(file.type) || validExtensions.includes(extension);
    };

    const handleUpload = async () => {
        if (!file || isLoading) return;

        try {
            const result = await onUpload(file);
            setUploadStatus({ success: true, message: result.message, stats: result.stats });
        } catch (error) {
            setUploadStatus({ success: false, message: error.message });
        }
    };

    const formatFileSize = (bytes) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    return (
        <div className="card">
            {/* Drop Zone */}
            <div
                className={`file-upload ${dragOver ? 'drag-over' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileSelect}
                />

                <Upload className="file-upload-icon" size={64} />
                <p className="file-upload-text">
                    Drag & drop your attendance file here
                </p>
                <p className="file-upload-hint">
                    or click to browse • CSV, XLSX, XLS formats supported
                </p>
            </div>

            {/* Selected File */}
            {file && (
                <div style={{
                    marginTop: 'var(--spacing-6)',
                    padding: 'var(--spacing-4)',
                    background: 'var(--color-surface-elevated)',
                    borderRadius: 'var(--radius-lg)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                }}>
                    <div className="flex items-center gap-4">
                        <FileSpreadsheet size={40} style={{ color: 'var(--color-status-green)' }} />
                        <div>
                            <p className="font-medium">{file.name}</p>
                            <p className="text-muted" style={{ fontSize: 'var(--font-size-sm)' }}>
                                {formatFileSize(file.size)}
                            </p>
                        </div>
                    </div>

                    <button
                        className="btn btn-primary"
                        onClick={handleUpload}
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <>
                                <span className="loading-spinner" style={{ width: '16px', height: '16px' }}></span>
                                Processing...
                            </>
                        ) : (
                            <>
                                <Upload size={18} />
                                Upload & Process
                            </>
                        )}
                    </button>
                </div>
            )}

            {/* Upload Status */}
            {uploadStatus && (
                <div style={{
                    marginTop: 'var(--spacing-4)',
                    padding: 'var(--spacing-4)',
                    background: uploadStatus.success
                        ? 'var(--color-status-green-bg)'
                        : 'var(--color-status-red-bg)',
                    borderRadius: 'var(--radius-lg)',
                    border: `1px solid ${uploadStatus.success
                        ? 'var(--color-status-green-border)'
                        : 'var(--color-status-red-border)'}`
                }}>
                    <div className="flex items-center gap-3">
                        {uploadStatus.success ? (
                            <Check size={20} style={{ color: 'var(--color-status-green)' }} />
                        ) : (
                            <AlertCircle size={20} style={{ color: 'var(--color-status-red)' }} />
                        )}
                        <div>
                            <p className="font-medium" style={{
                                color: uploadStatus.success
                                    ? 'var(--color-status-green)'
                                    : 'var(--color-status-red)'
                            }}>
                                {uploadStatus.message}
                            </p>

                            {uploadStatus.stats && (
                                <div style={{
                                    marginTop: 'var(--spacing-2)',
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                                    gap: 'var(--spacing-3)',
                                    fontSize: 'var(--font-size-sm)',
                                    color: 'var(--color-text-secondary)'
                                }}>
                                    <span>📊 Records: {uploadStatus.stats.records_parsed}</span>
                                    <span>📝 Logs Created: {uploadStatus.stats.attendance_logs_created}</span>
                                    <span>🔄 Duplicates Skipped: {uploadStatus.stats.attendance_logs_skipped_duplicates}</span>
                                    <span>📅 Daily Records: {uploadStatus.stats.daily_summaries_created}</span>
                                    <span>📈 Weekly Summaries: {uploadStatus.stats.weekly_summaries_created}</span>
                                    {uploadStatus.stats.employees_skipped_not_in_db > 0 && (
                                        <span style={{ color: 'var(--color-status-amber)' }}>
                                            ⚠️ Employees Not Found: {uploadStatus.stats.employees_skipped_not_in_db}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
