import React, { useState } from 'react';
import styled, { keyframes, createGlobalStyle } from 'styled-components';
import { useNavigate } from 'react-router-dom';
import ProustImage from './assets/proust.jpg';
import { theme } from './styles/theme';
import ReadingPaths, { ReadingPath } from './components/ReadingPaths';

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
  position: relative;
  overflow-x: hidden;
`;

const Hero = styled.section`
  padding: 4rem 2rem 2rem;
  text-align: center;
  animation: ${fadeIn} 0.8s ease-out;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    padding: 3rem 1rem 1rem;
  }
`;

const Header = styled.h1`
  font-family: ${theme.fonts.heading};
  font-size: clamp(2.5rem, 6vw, 4rem);
  margin: 0 0 1rem 0;
  font-weight: 400;
  letter-spacing: -0.02em;
`;

const Tagline = styled.p`
  font-size: clamp(1.1rem, 2vw, 1.4rem);
  color: ${theme.colors.textLight};
  margin: 0 auto 3rem;
  max-width: 600px;
  line-height: 1.6;
  font-style: italic;
`;

const ProustQuote = styled.blockquote`
  font-family: ${theme.fonts.secondary};
  font-style: italic;
  font-size: 1.1rem;
  color: ${theme.colors.primary};
  margin: 2rem auto;
  max-width: 800px;
  padding: 0 2rem;
  position: relative;
  
  &::before,
  &::after {
    content: '"';
    font-size: 3rem;
    color: rgba(139, 69, 19, 0.2);
    position: absolute;
  }
  
  &::before {
    top: -1rem;
    left: 0;
  }
  
  &::after {
    bottom: -2rem;
    right: 0;
  }
`;

const Section = styled.section`
  padding: 4rem 2rem;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    padding: 3rem 1rem;
  }
`;

const SectionTitle = styled.h2`
  font-family: ${theme.fonts.heading};
  font-size: 2.5rem;
  text-align: center;
  margin-bottom: 1rem;
  font-weight: 400;
`;

const SectionSubtitle = styled.p`
  text-align: center;
  color: ${theme.colors.textLight};
  font-size: 1.1rem;
  margin-bottom: 3rem;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
`;

const ModeSelector = styled.div`
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin-bottom: 3rem;
  flex-wrap: wrap;
`;

const ModeButton = styled.button<{ isActive: boolean }>`
  padding: 0.75rem 2rem;
  font-size: 1rem;
  font-family: ${theme.fonts.secondary};
  background: ${props => props.isActive ? theme.colors.primary : 'transparent'};
  color: ${props => props.isActive ? theme.colors.white : theme.colors.text};
  border: 2px solid ${theme.colors.primary};
  border-radius: 30px;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: ${theme.colors.primary};
    color: ${theme.colors.white};
    transform: translateY(-2px);
  }
`;

const StartButton = styled.button`
  display: block;
  margin: 3rem auto;
  padding: 1rem 3rem;
  font-size: 1.2rem;
  font-family: ${theme.fonts.secondary};
  background: ${theme.colors.primary};
  color: ${theme.colors.white};
  border: none;
  border-radius: 30px;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: #6b3410;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(139, 69, 19, 0.3);
  }
`;

const Navigation = styled.nav`
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  gap: 2rem;
  align-items: center;
  z-index: 10;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    gap: 1rem;
  }
`;

const NavLink = styled.a`
  text-decoration: none;
  color: ${theme.colors.text};
  font-family: ${theme.fonts.secondary};
  font-size: 1rem;
  transition: color ${theme.transitions.default};
  
  &:hover {
    color: ${theme.colors.primary};
  }
`;

const ProustImageFloating = styled.img`
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  opacity: 0.3;
  transition: all ${theme.transitions.default};
  
  &:hover {
    opacity: 0.8;
    transform: scale(1.1);
  }
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    width: 80px;
    height: 80px;
    bottom: 1rem;
    right: 1rem;
  }
`;

type ExperienceMode = 'guided' | 'explorer' | 'writer' | 'scholar';

const LandingPageRedesigned: React.FC = () => {
  const navigate = useNavigate();
  const [selectedMode, setSelectedMode] = useState<ExperienceMode>('guided');

  const readingPaths: ReadingPath[] = [
    {
      id: 'first-timer',
      title: "First Timer's Path",
      duration: '30-day journey',
      description: 'A gentle introduction to Proust through key themes and memorable passages',
      icon: '🌟',
      color: '#e8b04b',
      route: '/journey/first-timer'
    },
    {
      id: 'memory',
      title: 'Memory & Time Explorer',
      duration: '15-day deep dive',
      description: 'Uncover Proust\'s revolutionary treatment of memory and temporal experience',
      icon: '⏳',
      color: '#7a9cc6',
      route: '/journey/memory'
    },
    {
      id: 'characters',
      title: 'Character Connections',
      duration: 'Self-paced',
      description: 'Follow beloved characters through their journeys across all seven volumes',
      icon: '👥',
      color: '#9b7aa1',
      route: '/journey/characters'
    },
    {
      id: 'themes',
      title: 'Thematic Threads',
      duration: 'Modular paths',
      description: 'Explore love, jealousy, art, and society through connected passages',
      icon: '🎭',
      color: '#87a96b',
      route: '/journey/themes'
    },
    {
      id: 'daily',
      title: 'Daily Proust',
      duration: '365 days',
      description: 'One meaningful passage each day with context and commentary',
      icon: '📅',
      color: '#d68a59',
      route: '/journey/daily'
    },
    {
      id: 'custom',
      title: 'Create Your Path',
      duration: 'Personalized',
      description: 'Build a custom reading journey based on your interests and goals',
      icon: '✨',
      color: '#c17e7e',
      route: '/journey/custom'
    }
  ];

  const handlePathSelect = (path: ReadingPath) => {
    navigate('/chat', { 
      state: { 
        mode: 'guided_journey',
        journey: path.id,
        prompt: `Starting ${path.title}`
      } 
    });
  };

  const handleQuickStart = () => {
    switch (selectedMode) {
      case 'guided':
        navigate('/chat', { state: { mode: 'guided_journey' } });
        break;
      case 'explorer':
        navigate('/chat', { state: { mode: 'explore_lost_time' } });
        break;
      case 'writer':
        navigate('/chat', { state: { mode: 'writers_studio' } });
        break;
      case 'scholar':
        navigate('/chat', { state: { mode: 'scholar_mode' } });
        break;
    }
  };

  return (
    <>
      <GlobalStyle />
      <Container>
        <Navigation>
          <NavLink href="#about">About</NavLink>
          <NavLink href="#login">Sign In</NavLink>
        </Navigation>

        <Hero>
          <Header>Your Personal Guide Through Proust</Header>
          <Tagline>
            Actually read and understand "In Search of Lost Time" with AI-powered guidance
          </Tagline>
          <ProustQuote>
            The real voyage of discovery consists not in seeking new landscapes, but in having new eyes.
          </ProustQuote>
        </Hero>

        <Section>
          <SectionTitle>Choose Your Experience</SectionTitle>
          <SectionSubtitle>
            Four ways to explore Proust's masterwork, tailored to your goals
          </SectionSubtitle>
          
          <ModeSelector>
            <ModeButton 
              isActive={selectedMode === 'guided'}
              onClick={() => setSelectedMode('guided')}
            >
              📖 Guided Reader
            </ModeButton>
            <ModeButton 
              isActive={selectedMode === 'explorer'}
              onClick={() => setSelectedMode('explorer')}
            >
              🗺️ Explorer Mode
            </ModeButton>
            <ModeButton 
              isActive={selectedMode === 'writer'}
              onClick={() => setSelectedMode('writer')}
            >
              ✍️ Writer's Studio
            </ModeButton>
            <ModeButton 
              isActive={selectedMode === 'scholar'}
              onClick={() => setSelectedMode('scholar')}
            >
              🎓 Scholar Mode
            </ModeButton>
          </ModeSelector>

          {selectedMode === 'guided' && (
            <>
              <SectionSubtitle>
                Choose a structured path through Proust's world
              </SectionSubtitle>
              <ReadingPaths 
                paths={readingPaths} 
                onSelectPath={handlePathSelect}
              />
            </>
          )}

          {selectedMode === 'explorer' && (
            <div style={{ textAlign: 'center', maxWidth: '600px', margin: '0 auto' }}>
              <p style={{ fontSize: '1.1rem', lineHeight: '1.6' }}>
                Freely explore themes, characters, and passages. Create your own reading lists 
                and discover connections across all seven volumes.
              </p>
              <StartButton onClick={handleQuickStart}>
                Start Exploring
              </StartButton>
            </div>
          )}

          {selectedMode === 'writer' && (
            <div style={{ textAlign: 'center', maxWidth: '600px', margin: '0 auto' }}>
              <p style={{ fontSize: '1.1rem', lineHeight: '1.6' }}>
                Learn Proust's techniques through interactive tutorials. Practice extended metaphors, 
                sensory descriptions, and complex sentence construction.
              </p>
              <StartButton onClick={handleQuickStart}>
                Enter the Studio
              </StartButton>
            </div>
          )}

          {selectedMode === 'scholar' && (
            <div style={{ textAlign: 'center', maxWidth: '600px', margin: '0 auto' }}>
              <p style={{ fontSize: '1.1rem', lineHeight: '1.6' }}>
                Access academic annotations, critical essays, and cross-references with Proust's 
                letters and drafts. Perfect for research and deep study.
              </p>
              <StartButton onClick={handleQuickStart}>
                Begin Research
              </StartButton>
            </div>
          )}
        </Section>

        <ProustImageFloating src={ProustImage} alt="Marcel Proust" />
      </Container>
    </>
  );
};

export default LandingPageRedesigned;