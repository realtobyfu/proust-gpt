import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './style.css'; // Or './index.css' depending on your style preferences

ReactDOM.createRoot(document.getElementById('app') as HTMLElement).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
