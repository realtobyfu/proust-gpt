import React from 'react';
import LandingPage from './LandingPage';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import ChatPage from './ChatPage';
import AboutPage from './AboutPage';
import ReadPage from './ReadPage';
import { LanguageProvider } from './contexts/LanguageContext';
import './i18n';

const App: React.FC = () => {
    return (
        <LanguageProvider>
            <Router>
                <Routes>
                    <Route path="/" element={<LandingPage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/read" element={<ReadPage />} />
                    <Route path="/about" element={<AboutPage />} />
                </Routes>
            </Router>
        </LanguageProvider>
    );
};

export default App;
