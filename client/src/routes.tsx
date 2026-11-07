import { Outlet, type RouteObject } from 'react-router';


import Dashboard from './pages/Dashboard';
import HomePage from './pages/HomePage';
import Login from './pages/Login';

import Register from './pages/Register';
import ErrorPage from './pages/ErrorPage';
import LandingPage from './pages/LandingPage';
import ProtectedRoute from './components/ProtectedRoute';

const routes: RouteObject[] = [
  {
    path: '/',
    errorElement: <ErrorPage />, // Catches errors for all child routes below
    element: <Outlet />,         // Required to render the matched child route
    children: [
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/home',
        element: <HomePage />,
      },
      {
        path: '/dashboard',
        element: <Dashboard />,
      },
    ],
  },
  {
    path: '/login',
    element: <Login />,
  },

  {
    path: '/register',
    element: <Register />,
  },
],
},
];

export default routes;