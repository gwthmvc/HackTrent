import { useAuth0 } from '@auth0/auth0-react'
import { Navigate, Outlet } from 'react-router'

export default function ProtectedRoute() {
    const { isAuthenticated, isLoading } = useAuth0();

    if (isLoading) {
        return <p role="status" aria-live="polite">Loading your session...</p>;
    }

    return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
