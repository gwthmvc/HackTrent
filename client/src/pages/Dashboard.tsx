import '../styles/Dashboard.css'
import { useAuth0 } from '@auth0/auth0-react'


export default function Dashboard(){
    const { logout } = useAuth0();

    const handleLogout = () => {
        void logout({
            logoutParams: {
                returnTo: `${window.location.origin}/login`,
            },
        });
    };

    return(

        <>
        <title>Dashboard</title>
        <main className="dashboard-page">
            <h1>Dashboard</h1>
            <button type="button" onClick={handleLogout}>Log out</button>
        </main>
        </>
    )
}