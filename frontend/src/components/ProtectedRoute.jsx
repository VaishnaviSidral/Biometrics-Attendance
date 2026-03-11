import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function ProtectedRoute({ children, requireAdmin = false }) {
    const { loading, isAuthenticated, isAdmin, user } = useAuth();
    const location = useLocation();

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

    // If user is not admin and tries to access admin routes, redirect to employee dashboard
    if (!isAdmin && requireAdmin) {
        return <Navigate to="/employee-dashboard" replace />;
    }
    
    // Additional protection: Check if current path is admin-only
    const adminOnlyPaths = [
        '/', '/upload', '/employees', '/manage-employees', 
        '/settings', '/monthly-report/wfo', '/monthly-report/hybrid'
    ];
    
    const isCurrentPathAdminOnly = adminOnlyPaths.some(path => 
        location.pathname === path || location.pathname.startsWith(path + '/')
    );
    
    if (!isAdmin && isCurrentPathAdminOnly) {
        return <Navigate to="/employee-dashboard" replace />;
    }

    return children;
}
