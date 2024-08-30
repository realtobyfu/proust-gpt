import React from 'react';
import LandingPage from './LandingPage';
import { BrowserRouter as Router, Route, Routes, useNavigate } from 'react-router-dom';
import ChatPage from './ChatPage';

const App: React.FC = () => {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/chat" element={<ChatPage />} />
            </Routes>
        </Router>
    );
};

export default App;