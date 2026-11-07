import type { RouteObject } from 'react-router';

// import Home from './routes/Home';
// import About from './routes/About';
// import Dashboard from './routes/Dashboard';
import App from './App';

const routes: RouteObject[] = [
  {
    path: '/',
    element: <App />,
  },
//   {
//     path: '/about',
//     element: <About />,
//   },
//   {
//     path: '/dashboard',
//     element: <Dashboard />,
//   },
];

export default routes;