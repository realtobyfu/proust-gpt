import React, { useState } from 'react';
import styled, { css, keyframes, createGlobalStyle } from 'styled-components';
import { useNavigate } from 'react-router-dom';
import ProustImage from './assets/proust.jpg';
import { theme } from './styles/theme';

const GlobalStyle = createGlobalStyle`
  * {
    box-sizing: border-box;
  }
  
  body {
    margin: 0;
    padding: 0;
    font-family: ${theme.fonts.primary};
    background-color: ${theme.colors.background};
    color: ${theme.colors.text};
  }
`;

const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

const Container = styled.div`
  font-family: ${theme.fonts.primary};
  color: ${theme.colors.text};
  background-color: ${theme.colors.background};
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 2rem 5rem;
  position: relative;
  overflow: hidden;
  
  @media (max-width: ${theme.breakpoints.tablet}) {
    padding: 2rem 3rem;
  }
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    padding: 2rem 1.5rem;
    justify-content: flex-start;
    padding-top: 5rem;
  }
`;

const ContentWrapper = styled.div`
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  @media (max-width: ${theme.breakpoints.tablet}) {
    flex-direction: column;
    align-items: flex-start;
  }
`;

const MainContent = styled.div`
  flex: 1;
  animation: ${fadeIn} 0.8s ease-out;
`;

const Header = styled.h1`
  font-family: ${theme.fonts.heading};
  font-style: normal;
  font-weight: 400;
  font-size: clamp(3rem, 8vw, 4.5rem);
  margin: 0 0 2rem 0;
  text-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
  line-height: 1.1;
`;

const SubHeader = styled.p`
  font-size: clamp(1rem, 2vw, 1.2rem);
  color: ${theme.colors.textLight};
  margin-bottom: 1.5rem;
  max-width: 600px;
  line-height: 1.5;
`;

const Question = styled.p`
  font-family: ${theme.fonts.secondary};
  font-style: italic;
  font-weight: 400;
  font-size: clamp(1rem, 2vw, 1.1rem);
  color: ${theme.colors.primary};
  margin-bottom: 2rem;
`;

const ButtonContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  max-width: 600px;
  margin-bottom: 3rem;
`;

const Button = styled.button`
  font-family: ${theme.fonts.secondary};
  font-style: normal;
  font-weight: 400;
  color: ${theme.colors.text};
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid ${theme.colors.primary};
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  cursor: pointer;
  font-size: 1rem;
  text-align: left;
  transition: all ${theme.transitions.default};
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(139, 69, 19, 0.1), transparent);
    transition: left 0.5s;
  }

  &:hover {
    background-color: ${theme.colors.white};
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(139, 69, 19, 0.2);
    
    &::before {
      left: 100%;
    }
  }
  
  &:focus {
    outline: none;
    border-color: ${theme.colors.primary};
    box-shadow: 0 0 0 3px rgba(139, 69, 19, 0.3);
  }
`;

const ProustSection = styled.div`
  position: relative;
  animation: ${fadeIn} 0.8s ease-out 0.3s both;
  
  @media (min-width: ${theme.breakpoints.tablet}) {
    position: absolute;
    right: 5rem;
    top: 50%;
    transform: translateY(-50%);
  }
  
  @media (max-width: ${theme.breakpoints.tablet}) {
    margin-top: 3rem;
    align-self: center;
  }
`;

const ProustImageContainer = styled.div`
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  transition: transform ${theme.transitions.default};
  
  &:hover {
    transform: scale(1.05);
  }
`;

const ProustImageStyled = styled.img`
  width: clamp(200px, 30vw, 300px);
  height: auto;
  display: block;
`;

const FooterLink = styled.a`
  font-family: ${theme.fonts.secondary};
  font-style: normal;
  font-weight: 400;
  font-size: 1.1rem;
  color: ${theme.colors.text};
  text-decoration: none;
  position: absolute;
  bottom: 2rem;
  left: 5rem;
  transition: all ${theme.transitions.default};
  
  &:hover {
    color: ${theme.colors.primary};
    transform: translateX(4px);
  }
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    left: 1.5rem;
  }
`;

const LanguageSwitcher = styled.div`
  font-family: ${theme.fonts.secondary};
  font-style: normal;
  font-weight: 400;
  position: absolute;
  top: 2rem;
  right: 2rem;
  font-size: 1.1rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    top: 1rem;
    right: 1rem;
    font-size: 1rem;
  }
`;

const LanguageLink = styled.a<{ isActive?: boolean }>`
  text-decoration: none;
  color: ${props => props.isActive ? theme.colors.primary : theme.colors.text};
  transition: all ${theme.transitions.default};
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  
  &:hover {
    color: ${theme.colors.primary};
    background: rgba(139, 69, 19, 0.1);
  }
`;

const InfoModal = styled.div<{ isOpen: boolean }>`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: ${props => props.isOpen ? 'flex' : 'none'};
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
`;

const ModalContent = styled.div`
  background: ${theme.colors.white};
  border-radius: 16px;
  padding: 3rem;
  max-width: 600px;
  width: 100%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  animation: ${fadeIn} 0.3s ease-out;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: ${theme.colors.textLight};
  padding: 0.5rem;
  border-radius: 4px;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: rgba(0, 0, 0, 0.1);
  }
`;

const ModalTitle = styled.h2`
  font-family: ${theme.fonts.heading};
  font-size: 2rem;
  margin-bottom: 1.5rem;
  color: ${theme.colors.text};
`;

const ModalText = styled.p`
  line-height: 1.6;
  color: ${theme.colors.textLight};
  margin-bottom: 1rem;
`;

const LandingPageEnhanced: React.FC = () => {
    const navigate = useNavigate();
    const [isInfoOpen, setIsInfoOpen] = useState(false);
    const [language, setLanguage] = useState('EN');

    const handleButtonClick = (mode: string, prompt: string) => {
        navigate('/chat', { state: { mode, prompt } });
    };

    const toggleInfo = () => {
        setIsInfoOpen(!isInfoOpen);
    };

    return (
        <>
            <GlobalStyle />
            <Container>
                <LanguageSwitcher>
                    <LanguageLink href="#" onClick={toggleInfo}>INFO</LanguageLink>
                    <span>|</span>
                    <LanguageLink 
                        href="#" 
                        isActive={language === 'FR'}
                        onClick={(e) => { e.preventDefault(); setLanguage('FR'); }}
                    >
                        FR
                    </LanguageLink>
                    <LanguageLink 
                        href="#" 
                        isActive={language === 'EN'}
                        onClick={(e) => { e.preventDefault(); setLanguage('EN'); }}
                    >
                        EN
                    </LanguageLink>
                </LanguageSwitcher>

                <ContentWrapper>
                    <MainContent>
                        <Header>PROUST GPT</Header>
                        <SubHeader>
                            Explore Proust's masterpiece "In Search of Lost Time" and reflect on your day 
                            through the lens of one of literature's greatest minds.
                        </SubHeader>
                        <Question>How can I help you today?</Question>

                        <ButtonContainer>
                            <Button onClick={() => handleButtonClick('refine_prose', '')}>
                                Reflect on my day in Proust's style
                            </Button>
                            <Button onClick={() => handleButtonClick('explore_lost_time', '')}>
                                Explore "In Search of Lost Time"
                            </Button>
                            <Button onClick={() => handleButtonClick('explore_lost_time', 'Tell me about a place in Proust\'s world.')}>
                                Discover Proust's places
                            </Button>
                            <Button onClick={() => handleButtonClick('explore_lost_time', 'Tell me about memory and time in Proust.')}>
                                Explore memory and time
                            </Button>
                        </ButtonContainer>
                    </MainContent>

                    <ProustSection>
                        <ProustImageContainer>
                            <ProustImageStyled src={ProustImage} alt="Marcel Proust" />
                        </ProustImageContainer>
                    </ProustSection>
                </ContentWrapper>

                <FooterLink href="#">Combray →</FooterLink>

                <InfoModal isOpen={isInfoOpen} onClick={toggleInfo}>
                    <ModalContent onClick={(e) => e.stopPropagation()}>
                        <CloseButton onClick={toggleInfo}>×</CloseButton>
                        <ModalTitle>About ProustGPT</ModalTitle>
                        <ModalText>
                            ProustGPT is an AI-powered literary companion that brings Marcel Proust's 
                            "In Search of Lost Time" to life through modern technology.
                        </ModalText>
                        <ModalText>
                            <strong>Explore Lost Time:</strong> Ask questions about Proust's work and receive 
                            relevant passages from the text, powered by semantic search and retrieval.
                        </ModalText>
                        <ModalText>
                            <strong>Reflect on Your Day:</strong> Engage in thoughtful conversation about your 
                            daily experiences, guided by AI that embodies Proust's introspective style.
                        </ModalText>
                        <ModalText>
                            Built with React, Flask, and advanced language models, ProustGPT bridges the gap 
                            between classic literature and modern AI technology.
                        </ModalText>
                    </ModalContent>
                </InfoModal>
            </Container>
        </>
    );
};

export default LandingPageEnhanced;