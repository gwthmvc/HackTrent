import { useAuth0 } from '@auth0/auth0-react'
import { Navigate, Outlet } from 'react-router'

export default function ProtectedRoute() {
    const { isAuthenticated, isLoading } = useAuth0();
    const shouldReturnToHome = sessionStorage.getItem('smartmove_login_return_to_home') === 'true';

    if (isLoading) {
        return <p role="status" aria-live="polite">Loading your session...</p>;
    }

    if (isAuthenticated && shouldReturnToHome) {
        sessionStorage.removeItem('smartmove_login_return_to_home');
        return <Navigate to="/home" replace />;
    }

    return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
