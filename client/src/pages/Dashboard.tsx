import '../styles/Dashboard.css'
import { useNavigate } from 'react-router'


export default function Dashboard(){
    const navigate = useNavigate();

    const handleLogout = () => {
        localStorage.clear();
        navigate('/login');
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