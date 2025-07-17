import React from 'react';
import LandingPageRefined from './LandingPageRefined';
import { BrowserRouter as Router, Route, Routes, useNavigate } from 'react-router-dom';
import ChatPageRefined from './ChatPageRefined';

const App: React.FC = () => {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<LandingPageRefined />} />
                <Route path="/chat" element={<ChatPageRefined />} />
            </Routes>
        </Router>
    );
};

export default App;