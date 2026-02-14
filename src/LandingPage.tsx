import React, { useState, useEffect, useRef, useMemo } from 'react';
import styled from 'styled-components';
import { useNavigate, Link } from 'react-router-dom';
import ProustImage from './assets/proust.jpg';

// ── Helpers ───────────────────────────────────────────────────────────────────

function shuffleArray<T>(arr: T[]): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// ── Data ──────────────────────────────────────────────────────────────────────

const EXPLORE_PROMPTS = [
  { text: 'The madeleine scene', prompt: 'What is the madeleine scene really about?' },
  { text: 'Swann and Odette', prompt: "How does Swann's love for Odette change over time?" },
  { text: 'The role of memory', prompt: 'How does Proust explore the role of memory?' },
  { text: 'The two ways', prompt: "What are the two 'ways' at Combray?" },
  { text: 'Jealousy in Proust', prompt: 'How does Proust portray jealousy?' },
  { text: 'Time and aging', prompt: 'How does Proust explore the passage of time and aging?' },
  { text: 'Art and beauty', prompt: 'What role does art play in the novel?' },
  { text: 'Sleep and dreams', prompt: 'How does Proust describe sleep and dreams?' },
];

const REFLECT_PROMPTS = [
  { text: 'A taste that brought back a place', prompt: 'A taste that brought back a forgotten place' },
  { text: 'Someone I love has changed', prompt: 'I noticed someone I love has changed' },
  { text: 'A place I can never return to', prompt: 'There is a place I can never return to' },
  { text: 'A moment I wish I could relive', prompt: 'There is a moment I wish I could relive' },
];

// ── Styled Components ─────────────────────────────────────────────────────────

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

  @media (max-width: 1024px) {
    padding-left: 3rem;
  }

  @media (max-width: 768px) {
    padding-left: 1.5rem;
    padding-right: 1.5rem;
    padding-top: 4rem;
    justify-content: flex-start;
  }
`;

const Header = styled.h1`
  margin-bottom: 2rem;
  margin-left: 1rem;
  font-family: "Belgrano", serif;
  font-style: normal;
  font-weight: 400;
  font-size: 4.5rem;
  text-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);

  @media (max-width: 1024px) {
    font-size: 3.5rem;
  }

  @media (max-width: 768px) {
    font-size: 2.8rem;
    margin-left: 0;
  }
`;

const SubHeader = styled.p`
  margin-left: 1rem;
  font-size: 1.2rem;
  color: #555;
  margin-bottom: 20px;

  @media (max-width: 768px) {
    margin-left: 0;
    font-size: 1.05rem;
  }
`;

const Question = styled.p`
  font-family: 'IBM Plex Sans', serif;
  font-style: italic;
  font-weight: 400;
  margin-left: 1rem;
  font-size: 1.1rem;
  color: #2a2a2a;
  margin-bottom: 10px;

  @media (max-width: 768px) {
    margin-left: 0;
  }
`;

const SearchForm = styled.form`
  margin-left: 1rem;
  margin-top: 0.75rem;
  margin-bottom: 1.5rem;
  max-width: 28rem;

  @media (max-width: 768px) {
    margin-left: 0;
    max-width: 100%;
  }
`;

const SearchInputPill = styled.div`
  display: flex;
  align-items: center;
  position: relative;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid #d4ccc3;
  border-radius: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;

  &:focus-within {
    border-color: #8b4513;
    box-shadow: 0 4px 20px rgba(139, 69, 19, 0.1);
  }
`;

const SearchInput = styled.input`
  width: 100%;
  padding: 0.8rem 3.2rem 0.8rem 1.1rem;
  border: none;
  border-radius: 24px;
  font-size: 0.95rem;
  color: #333;
  background: transparent;
  font-family: 'Georgia', serif;

  &::placeholder {
    color: #a89888;
    font-style: italic;
  }

  &:focus {
    outline: none;
  }
`;

const SearchSendButton = styled.button`
  position: absolute;
  right: 6px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background-color: #8b4513;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #6b3410;
  }
`;

const ButtonContainer = styled.div<{ $noWrap?: boolean }>`
  display: flex;
  justify-content: flex-start;
  gap: 12px;
  flex-wrap: ${props => props.$noWrap ? 'nowrap' : 'wrap'};
  margin-bottom: 0.5rem;
  max-width: 36rem;
  padding-left: 1rem;

  @media (max-width: 768px) {
    padding-left: 0;
    max-width: 100%;
    flex-wrap: wrap;
  }
`;

const Button = styled.button<{ $mode?: 'explore' | 'reflect' }>`
  font-family: 'IBM Plex Sans', serif;
  font-style: normal;
  font-weight: 400;
  color: ${props => props.$mode === 'reflect' ? '#4a5a4a' : '#3a3028'};
  background: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.06)' : 'rgba(58, 48, 40, 0.04)'};
  border: 1px solid ${props => props.$mode === 'reflect' ? '#8a9b8a' : '#3a3028'};
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  font-size: 0.95rem;
  text-align: center;
  transition: all 0.2s ease;

  &:hover {
    background-color: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.14)' : '#f1ede9'};
    transform: translateY(-1px);
    box-shadow: 0 2px 8px ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.15)' : 'rgba(58, 48, 40, 0.15)'};
  }

  &:focus {
    outline: none;
    border-color: ${props => props.$mode === 'reflect' ? '#5a6b5a' : '#564a40'};
    box-shadow: 0 0 0 3px ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.2)' : 'rgba(58, 48, 40, 0.2)'};
  }

  @media (max-width: 768px) {
    flex: 1 1 calc(50% - 6px);
    min-width: 0;
  }
`;

const ModeDivider = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  max-width: 28rem;
  padding-left: 1rem;
  margin: 0.75rem 0;

  &::before,
  &::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #d4ccc3;
  }

  @media (max-width: 768px) {
    padding-left: 0;
    max-width: 100%;
  }
`;

const ModeDividerText = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.8rem;
  color: #999;
  white-space: nowrap;
`;

const ProustSection = styled.div`
  position: absolute;
  right: 8rem;
  top: 20rem;
  display: flex;
  flex-direction: column;
  align-items: center;

  @media (max-width: 1024px) {
    right: 3rem;
    top: 18rem;
  }

  @media (max-width: 768px) {
    display: none;
  }
`;

const ProustImageContainer = styled.img`
  width: 15rem;
  height: auto;
  border-radius: 8px;
  opacity: 0.85;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  transition: opacity 0.3s ease;

  @media (max-width: 1024px) {
    width: 12rem;
  }

  &:hover {
    opacity: 1;
  }
`;

const TopNavLinks = styled.div`
  position: absolute;
  top: 1.5rem;
  right: 2rem;
  display: flex;
  gap: 1.5rem;
  align-items: center;
  z-index: 10;
`;

const NavLink = styled(Link)`
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 400;
  font-size: 1rem;
  color: #8b4513;
  text-decoration: none;

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

  a {
    color: #8b4513;
    text-decoration: underline;
    cursor: pointer;

    &:hover {
      color: #6b3410;
    }
  }
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
  margin-top: 1.25rem;
  margin-left: 1rem;

  &:hover {
    text-decoration: underline;
  }

  @media (max-width: 768px) {
    margin-left: 0;
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

// ── Component ─────────────────────────────────────────────────────────────────

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState('');
  const [showGuidance, setShowGuidance] = useState(false);
  const [hasHistory, setHasHistory] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const exploreChips = useMemo(() => shuffleArray(EXPLORE_PROMPTS).slice(0, 3), []);
  const reflectChips = useMemo(() => shuffleArray(REFLECT_PROMPTS).slice(0, 2), []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem('proust-sessions-index');
      const sessions = raw ? JSON.parse(raw) : [];
      setHasHistory(sessions.some((s: any) => s.messageCount > 0));
    } catch { /* ignore */ }
  }, []);

  // autoFocus only on desktop
  useEffect(() => {
    if (window.innerWidth >= 1025 && inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    navigate('/chat', { state: { mode: 'explore_lost_time', prompt: inputValue.trim() } });
  };

  const handleChipClick = (mode: string, prompt: string) => {
    navigate('/chat', { state: { mode, prompt } });
  };

  const handleGuidanceExplore = (prompt: string) => {
    navigate('/chat', { state: { mode: 'explore_lost_time', prompt } });
  };

  return (
    <Container>
      <TopNavLinks>
        <NavLink to="/read">Read</NavLink>
        <NavLink to="/about">About</NavLink>
      </TopNavLinks>

      <Header>PROUST GPT</Header>
      <SubHeader>Explore Proust's literature with AI</SubHeader>
      <Question>What would you like to explore?</Question>

      <SearchForm onSubmit={handleSearchSubmit}>
        <SearchInputPill>
          <SearchInput
            ref={inputRef}
            type="text"
            placeholder="Ask about a theme, character, or passage..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
          />
          <SearchSendButton type="submit" aria-label="Search">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </SearchSendButton>
        </SearchInputPill>
      </SearchForm>

      <ButtonContainer>
        {exploreChips.map((chip) => (
          <Button
            key={chip.text}
            $mode="explore"
            onClick={() => handleChipClick('explore_lost_time', chip.prompt)}
          >
            {chip.text}
          </Button>
        ))}
      </ButtonContainer>

      <ModeDivider>
        <ModeDividerText>or reflect on your own experience</ModeDividerText>
      </ModeDivider>

      <ButtonContainer $noWrap>
        {reflectChips.map((chip) => (
          <Button
            key={chip.text}
            $mode="reflect"
            onClick={() => handleChipClick('refine_prose', chip.prompt)}
          >
            {chip.text}
          </Button>
        ))}
      </ButtonContainer>

      <ReadLink to="/read">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2" strokeLinecap="round"
             strokeLinejoin="round">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
        </svg>
        Begin reading
      </ReadLink>

      <GuidanceToggle onClick={() => setShowGuidance(!showGuidance)}>
        {showGuidance ? 'Hide' : 'New to Proust?'}
      </GuidanceToggle>

      <GuidanceSection $visible={showGuidance}>
        Begin with <em>Swann's Way</em>, the first volume. Follow young Marcel's memories
        of childhood in Combray. Discover the famous{' '}
        <a onClick={() => handleGuidanceExplore('What is the madeleine scene really about?')}>
          madeleine scene
        </a>{' '}
        that unlocks the nature of involuntary memory. Or explore any theme, character, or
        passage that interests you.
      </GuidanceSection>

      <ProustSection>
        <ProustImageContainer src={ProustImage} alt="Marcel Proust" />
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
