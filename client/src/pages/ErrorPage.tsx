import { isRouteErrorResponse, Link, useRouteError } from 'react-router'

export default function ErrorPage(){
    const error = useRouteError();
    const message = isRouteErrorResponse(error)
        ? `${error.status} ${error.statusText}`
        : 'Something went wrong while loading this page.';

    return (
        <>
            <title>Error | HackTrent</title>
            <main aria-labelledby="error-heading">
                <h1 id="error-heading">Something went wrong</h1>
                <p>{message}</p>
                <Link to="/">Return to HackTrent</Link>
            </main>
        </>
    );
}