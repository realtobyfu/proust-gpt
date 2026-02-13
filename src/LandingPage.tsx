import React, { useState } from 'react';
import styled, { css } from 'styled-components';
import { useNavigate } from 'react-router-dom';
import ProustImage from './assets/proust.jpg';

const Container = styled.div`
  font-family: 'Georgia', serif;
  color: #333;
  background-color: #f7f4f0;
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-left: 5rem;
  position: relative;
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
  margin-bottom: 8rem;
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
  }
  
  &:focus {
    outline: none;
    border-color: #8b4513;
    box-shadow: 0 0 0 3px rgba(139, 69, 19, 0.3);
  }
`;

const ProustSection = styled.div`
  position: absolute;
  right: 4rem;
  top: 20rem;
`;

const ProustImageContainer = styled.img`
  width: 15rem;
  height: auto;
  border-radius: 5px;
  opacity: 0.9;
  transition: opacity 0.3s ease;
  
  &:hover {
    opacity: 1;
  }
`;


const LanguageSwitcher = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-style: normal;
  font-weight: 400;
  position: absolute;
  top: 20px;
  right: 20px;
  font-size: 1.1rem;
`;

const LanguageLink = styled.a<{ $inactive?: boolean }>`
  text-decoration: none;
  color: #333;
  transition: color 0.2s ease;

  ${({ $inactive }) =>
    $inactive &&
    css`
      color: rgba(0, 0, 0, 0.3);
    `}

  &:hover {
    color: #8b4513;
  }
`;

const GuidanceSection = styled.div<{ $visible: boolean }>`
  margin-left: 1rem;
  margin-top: -0.5rem;
  margin-bottom: 1.5rem;
  max-width: 40rem;
  font-size: 0.95rem;
  line-height: 1.6;
  color: #666;
  height: ${props => props.$visible ? 'auto' : '0'};
  opacity: ${props => props.$visible ? '1' : '0'};
  overflow: hidden;
  transition: all 0.3s ease;
`;

const GuidanceToggle = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  cursor: pointer;
  text-decoration: underline;
  margin-left: 1rem;
  margin-bottom: 1rem;
  padding: 0;
  
  &:hover {
    color: #6b3410;
  }
`;

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [showGuidance, setShowGuidance] = useState(false);
  const [currentLang, setCurrentLang] = useState('EN');

  const handleButtonClick = (mode: string, prompt: string) => {
    navigate('/chat', { state: { mode, prompt } });
  };

  return (
    <Container>
      <LanguageSwitcher>
        <LanguageLink as="span" onClick={() => navigate('/about')} style={{ cursor: 'pointer' }}>About</LanguageLink>
        <span style={{ margin: '0 1rem' }}>|</span>
        <LanguageLink 
          href="#" 
          $inactive={currentLang !== 'FR'}
          onClick={(e) => { e.preventDefault(); setCurrentLang('FR'); }}
        >
          FR
        </LanguageLink>
        <span style={{ margin: '0 0.5rem' }}>|</span>
        <LanguageLink 
          href="#" 
          $inactive={currentLang !== 'EN'}
          onClick={(e) => { e.preventDefault(); setCurrentLang('EN'); }}
        >
          EN
        </LanguageLink>
      </LanguageSwitcher>

      <Header>PROUST GPT</Header>
      <SubHeader>Explore Proust's literature using a language model</SubHeader>
      <Question>How can I help you today?</Question>

      <GuidanceToggle onClick={() => setShowGuidance(!showGuidance)}>
        {showGuidance ? 'Hide guidance' : 'New to Proust?'}
      </GuidanceToggle>
      
      <GuidanceSection $visible={showGuidance}>
        Begin with Swann's Way, the first volume. Follow young Marcel's memories 
        of childhood in Combray. Discover the famous madeleine scene that unlocks 
        the nature of involuntary memory. Or explore any theme, character, or 
        passage that interests you.
      </GuidanceSection>

      <ButtonContainer>
        <Button onClick={() => handleButtonClick('explore_lost_time', 'I want to begin reading In Search of Lost Time')}>
          Begin reading Proust
        </Button>
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

      <ProustSection>
        <ProustImageContainer src={ProustImage} alt="Marcel Proust" />
      </ProustSection>
    </Container>
  );
};

export default LandingPage;