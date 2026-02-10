import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function ProtectedRoute({ children, requireAdmin = false }) {
    const { loading, isAuthenticated, isAdmin, user } = useAuth();

    if (loading) {
        return (
            <div className="loading-overlay">
                <div className="loading-spinner"></div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    if (requireAdmin && !isAdmin) {
        return (
            <div className="empty-state">
                <h2 className="empty-state-title">Access Denied</h2>
                <p className="empty-state-text">
                    You do not have permission to access this page.
                </p>
                <p className="text-muted">
                    Logged in as: {user?.username} ({user?.role})
                </p>
            </div>
        );
    }

    return children;
}
