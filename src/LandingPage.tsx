import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { useNavigate, Link } from 'react-router-dom';
import ProustImage from './assets/proust.jpg';

const Container = styled.div`
  font-family: 'Georgia', serif;
  color: #333;
  background-color: #f7f4f0;
  min-height: 100vh;
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-left: 5rem;
  position: relative;
  overflow-x: hidden;
`;

const Header = styled.h1`
  margin-bottom: 2rem;
  margin-left: 1rem;
  font-family: "Belgrano", serif;
  font-style: normal;
  font-weight: 400;
  font-size: 4.5rem;
  text-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
`;

const SubHeader = styled.p`
  margin-left: 1rem;
  font-size: 1.2rem;
  color: #555;
  margin-bottom: 20px;
`;

const Question = styled.p`
  font-family: 'IBM Plex Sans', serif;
  font-style: italic;
  font-weight: 400;
  margin-left: 1rem;
  font-size: 1.1rem;
  color: #8b4513;
  margin-bottom: 10px;
`;

const ButtonContainer = styled.div`
  margin-top: 1rem;
  display: flex;
  justify-content: flex-start;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
  max-width: 30rem;
  padding-left: 2rem;
`;

const Button = styled.button`
  font-family: 'IBM Plex Sans', serif;
  font-style: normal;
  font-weight: 400;
  color: #1a1a1a;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid #8b4513;
  border-radius: 10px;
  padding: 15px;
  cursor: pointer;
  font-size: 1rem;
  width: 200px;
  text-align: center;
  transition: all 0.2s ease;

  &:hover {
    background-color: #f1ede9;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(139, 69, 19, 0.15);
  }
  
  &:focus {
    outline: none;
    border-color: #8b4513;
    box-shadow: 0 0 0 3px rgba(139, 69, 19, 0.3);
  }
`;

const ProustSection = styled.div`
  position: absolute;
  right: 8rem;
  top: 20rem;
  display: flex;
  flex-direction: column;
  align-items: center;
`;

const ProustImageContainer = styled.img`
  width: 15rem;
  height: auto;
  border-radius: 8px;
  opacity: 0.85;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  transition: opacity 0.3s ease;

  &:hover {
    opacity: 1;
  }
`;


const AboutLink = styled(Link)`
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 400;
  position: absolute;
  top: 1.5rem;
  right: 2rem;
  font-size: 1rem;
  color: #8b4513;
  text-decoration: none;
  z-index: 10;

  &:hover {
    text-decoration: underline;
  }
`;

const GuidanceSection = styled.div<{ $visible: boolean }>`
  position: fixed;
  bottom: 5rem;
  left: 2rem;
  max-width: 24rem;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #666;
  background: #f7f4f0;
  padding: ${props => props.$visible ? '1rem' : '0'};
  border-radius: 8px;
  box-shadow: ${props => props.$visible ? '0 2px 8px rgba(0,0,0,0.1)' : 'none'};
  height: ${props => props.$visible ? 'auto' : '0'};
  opacity: ${props => props.$visible ? '1' : '0'};
  overflow: hidden;
  transition: all 0.3s ease;
  z-index: 100;
`;

const GuidanceToggle = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  cursor: pointer;
  text-decoration: underline;
  position: fixed;
  bottom: 3rem;
  left: 2rem;
  padding: 0.5rem 0;
  outline: none;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  z-index: 100;

  &:focus, &:focus-visible {
    outline: none;
  }

  &:hover {
    color: #6b3410;
  }
`;

const ReadLink = styled(Link)`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.95rem;
  color: #8b4513;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.75rem;

  &:hover {
    text-decoration: underline;
  }
`;

const FloatingChatButton = styled.button`
  position: fixed;
  bottom: 3rem;
  right: 2rem;
  width: 56px;
  height: 56px;
  background-color: #8b4513;
  color: #fff;
  border: none;
  border-radius: 50%;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(139, 69, 19, 0.3);
  transition: all 0.2s ease;
  z-index: 100;

  &:hover {
    background-color: #6b3410;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(139, 69, 19, 0.4);
  }
`;

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [showGuidance, setShowGuidance] = useState(false);
  const [hasHistory, setHasHistory] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem('proust-sessions-index');
      const sessions = raw ? JSON.parse(raw) : [];
      setHasHistory(sessions.some((s: any) => s.messageCount > 0));
    } catch { /* ignore */ }
  }, []);

  const handleButtonClick = (mode: string, prompt: string) => {
    navigate('/chat', { state: { mode, prompt } });
  };

  return (
    <Container>
      <AboutLink to="/about">About</AboutLink>

      <Header>PROUST GPT</Header>
      <SubHeader>Explore Proust's literature using a language model</SubHeader>
      <Question>How can I help you today?</Question>

      <ButtonContainer>
        <Button onClick={() => handleButtonClick('explore_lost_time', '')}>
          Explore passages
        </Button>
        <Button onClick={() => handleButtonClick('refine_prose', '')}>
          Reflect in Proust's style
        </Button>
        <Button onClick={() => handleButtonClick('explore_lost_time', 'Tell me about memory in Proust')}>
          Study a theme
        </Button>
      </ButtonContainer>

      <GuidanceToggle onClick={() => setShowGuidance(!showGuidance)}>
        {showGuidance ? 'Hide' : 'New to Proust?'}
      </GuidanceToggle>

      <GuidanceSection $visible={showGuidance}>
        Begin with Swann's Way, the first volume. Follow young Marcel's memories
        of childhood in Combray. Discover the famous madeleine scene that unlocks
        the nature of involuntary memory. Or explore any theme, character, or
        passage that interests you.
      </GuidanceSection>

      <ProustSection>
        <ProustImageContainer src={ProustImage} alt="Marcel Proust" />
        <ReadLink to="/read">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round"
               strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
          Begin reading
        </ReadLink>
      </ProustSection>

      {hasHistory && (
        <FloatingChatButton onClick={() => navigate('/chat', { state: { mode: 'explore_lost_time', prompt: '' } })}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round"
               strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </FloatingChatButton>
      )}
    </Container>
  );
};

export default LandingPage;