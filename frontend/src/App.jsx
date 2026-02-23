import { BrowserRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import UploadData from './pages/UploadData';
import AllEmployees from './pages/AllEmployees';
import IndividualReport from './pages/IndividualReport';
import Settings from './pages/Settings';
import MonthlyReport from './pages/MonthlyReport';
import EmployeeDashboard from './pages/EmployeeDashboard';

function Layout() {
  const location = useLocation();
  const { isAuthenticated, isAdmin, isEmployee } = useAuth();

  const getCurrentPageTitle = () => {
    const path = location.pathname;
    const titles = {
      '/': 'Dashboard',
      '/upload': 'Upload Data',
      '/employees': 'All Employees',
      '/monthly-report/wfo': 'Monthly Report — WFO',
      '/monthly-report/hybrid': 'Monthly Report — Hybrid',
      '/settings': 'Settings',
      '/employee-dashboard': 'My Attendance'
    };

    if (path.startsWith('/employee/')) {
      return 'Employee Report';
    }

    return titles[path] || 'Dashboard';
  };

  // Show sidebar only for admin users
  const showSidebar = isAuthenticated && isAdmin;

  return (
    <div className="app-container">
      {showSidebar && <Sidebar />}
      {isAuthenticated && <Header title={getCurrentPageTitle()} />}
      <main className={`main-content ${!showSidebar ? 'no-sidebar' : ''}`}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />

          {/* Employee routes */}
          <Route
            path="/employee-dashboard"
            element={
              <ProtectedRoute>
                <EmployeeDashboard />
              </ProtectedRoute>
            }
          />

          {/* Admin routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute requireAdmin>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute requireAdmin>
                <UploadData />
              </ProtectedRoute>
            }
          />
          <Route
            path="/employees"
            element={
              <ProtectedRoute requireAdmin>
                <AllEmployees />
              </ProtectedRoute>
            }
          />
          <Route
            path="/monthly-report"
            element={<Navigate to="/monthly-report/wfo" replace />}
          />
          <Route
            path="/monthly-report/wfo"
            element={
              <ProtectedRoute requireAdmin>
                <MonthlyReport workMode="WFO" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/monthly-report/hybrid"
            element={
              <ProtectedRoute requireAdmin>
                <MonthlyReport workMode="HYBRID" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/:code"
            element={
              <ProtectedRoute requireAdmin>
                <IndividualReport />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute requireAdmin>
                <Settings />
              </ProtectedRoute>
            }
          />

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
