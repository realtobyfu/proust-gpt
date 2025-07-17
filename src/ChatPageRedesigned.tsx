import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import styled, { createGlobalStyle } from 'styled-components';
import LoadingDots from './components/LoadingDots';
import { theme } from './styles/theme';
import JourneyMap from './components/JourneyMap';
import EnhancedPassageDisplay from './components/EnhancedPassageDisplay';
import { useLocalStorage } from './hooks/useLocalStorage';

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

const ChatContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: ${theme.colors.background};
  position: relative;
`;

const Sidebar = styled.div<{ isOpen: boolean }>`
  width: 320px;
  background-color: ${theme.colors.white};
  border-right: 1px solid ${theme.colors.border};
  display: flex;
  flex-direction: column;
  transition: transform ${theme.transitions.default};
  
  @media (max-width: ${theme.breakpoints.tablet}) {
    position: fixed;
    left: 0;
    top: 0;
    height: 100%;
    transform: translateX(${props => props.isOpen ? '0' : '-100%'});
    z-index: 100;
    box-shadow: ${props => props.isOpen ? '2px 0 10px rgba(0,0,0,0.1)' : 'none'};
  }
`;

const SidebarHeader = styled.div`
  padding: 2rem;
  border-bottom: 1px solid ${theme.colors.border};
`;

const SidebarContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
`;

const MainArea = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
`;

const Header = styled.div`
  background: ${theme.colors.white};
  border-bottom: 1px solid ${theme.colors.border};
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const ContentArea = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
`;

const JourneyMapContainer = styled.div<{ isVisible: boolean }>`
  display: ${props => props.isVisible ? 'block' : 'none'};
  margin-bottom: 2rem;
`;

const MessagesContainer = styled.div`
  max-width: 900px;
  margin: 0 auto;
`;

const Message = styled.div<{ isUser: boolean }>`
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  align-items: flex-start;
  ${props => props.isUser && 'flex-direction: row-reverse;'}
`;

const Avatar = styled.div<{ isUser: boolean }>`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: ${props => props.isUser ? theme.colors.primary : '#ddd'};
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  flex-shrink: 0;
`;

const MessageContent = styled.div<{ isUser: boolean }>`
  flex: 1;
  padding: 1rem 1.5rem;
  background: ${props => props.isUser ? theme.colors.userMessageBg : theme.colors.proustMessageBg};
  border-radius: 16px;
  ${props => props.isUser && 'text-align: right;'}
`;

const InputContainer = styled.div`
  background: ${theme.colors.white};
  border-top: 1px solid ${theme.colors.border};
  padding: 1.5rem 2rem;
`;

const InputWrapper = styled.div`
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  gap: 1rem;
`;

const Input = styled.textarea`
  flex: 1;
  padding: 1rem;
  border: 1px solid ${theme.colors.border};
  border-radius: 8px;
  font-family: ${theme.fonts.primary};
  font-size: 1rem;
  resize: none;
  min-height: 60px;
  max-height: 200px;
  
  &:focus {
    outline: none;
    border-color: ${theme.colors.primary};
  }
`;

const SubmitButton = styled.button`
  padding: 1rem 2rem;
  background: ${theme.colors.primary};
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover:not(:disabled) {
    background: #6b3410;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const QuickActions = styled.div`
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
`;

const QuickActionButton = styled.button`
  padding: 0.5rem 1rem;
  background: rgba(139, 69, 19, 0.1);
  border: 1px solid ${theme.colors.primary};
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: ${theme.colors.primary};
    color: white;
  }
`;

const ModeIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
`;

const ReadingAidsPanel = styled.div`
  background: rgba(247, 244, 240, 0.8);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
`;

const AidTitle = styled.h4`
  font-size: 1rem;
  margin-bottom: 1rem;
  color: ${theme.colors.text};
`;

const CharacterList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
`;

const CharacterItem = styled.div`
  padding: 0.5rem;
  background: white;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    transform: translateX(4px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
`;

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
  passages?: any[];
}

const ChatPageRedesigned: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { state } = location;
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const [messages, setMessages] = useLocalStorage<Message[]>('proust-messages', []);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showJourneyMap, setShowJourneyMap] = useState(false);
  const [currentVolume, setCurrentVolume] = useState(1);
  
  const mode = state?.mode || 'explore_lost_time';
  const journey = state?.journey;

  useEffect(() => {
    if (state?.prompt) {
      setInputValue(state.prompt);
    }
    
    if (mode === 'guided_journey') {
      setShowJourneyMap(true);
    }
  }, [state]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getModeDisplay = () => {
    switch (mode) {
      case 'guided_journey':
        return { icon: '📖', label: 'Guided Journey' };
      case 'explore_lost_time':
        return { icon: '🗺️', label: 'Explorer Mode' };
      case 'writers_studio':
        return { icon: '✍️', label: "Writer's Studio" };
      case 'scholar_mode':
        return { icon: '🎓', label: 'Scholar Mode' };
      case 'refine_prose':
        return { icon: '💭', label: 'Reflect on My Day' };
      default:
        return { icon: '📚', label: 'Reading Proust' };
    }
  };

  const handleSubmit = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputValue,
      isUser: true,
      timestamp: new Date()
    };

    setMessages([...messages, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const endpoint = mode === 'refine_prose' ? '/api/reflect' : '/api/explore_lost_time';
      const response = await fetch(`http://localhost:5000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage.text })
      });

      const data = await response.json();
      
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: data.reply || data.passages?.[0]?.text || 'No response',
        isUser: false,
        timestamp: new Date(),
        passages: data.passages
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const quickActions = {
    guided_journey: [
      "What happens next in my journey?",
      "Explain this passage's significance",
      "Show me related themes",
      "Who are these characters?"
    ],
    explore_lost_time: [
      "Tell me about involuntary memory",
      "Describe the madeleine scene",
      "What is Swann's Way about?",
      "Explain time in Proust"
    ],
    writers_studio: [
      "Show me an example of extended metaphor",
      "How does Proust build complex sentences?",
      "Teach me about sensory description",
      "Analyze my writing style"
    ],
    scholar_mode: [
      "Show critical interpretations",
      "Compare translations",
      "Explain historical context",
      "Find scholarly references"
    ]
  };

  const prominentCharacters = [
    "Marcel (Narrator)",
    "Swann",
    "Odette",
    "Gilberte",
    "Albertine",
    "Baron de Charlus",
    "Duchess de Guermantes"
  ];

  return (
    <>
      <GlobalStyle />
      <ChatContainer>
        <Sidebar isOpen={sidebarOpen}>
          <SidebarHeader>
            <h2 style={{ margin: 0, fontFamily: theme.fonts.heading }}>ProustGPT</h2>
            <button 
              onClick={() => navigate('/')}
              style={{ 
                marginTop: '1rem',
                background: 'none',
                border: `1px solid ${theme.colors.primary}`,
                borderRadius: '8px',
                padding: '0.5rem 1rem',
                cursor: 'pointer'
              }}
            >
              ← Back to Home
            </button>
          </SidebarHeader>
          
          <SidebarContent>
            {mode === 'guided_journey' && (
              <ReadingAidsPanel>
                <AidTitle>📚 Reading Progress</AidTitle>
                <p style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
                  Volume {currentVolume} of 7
                </p>
                <div style={{ background: '#ddd', height: '4px', borderRadius: '2px' }}>
                  <div 
                    style={{ 
                      background: theme.colors.primary, 
                      height: '100%', 
                      width: '35%',
                      borderRadius: '2px',
                      transition: 'width 0.3s'
                    }} 
                  />
                </div>
              </ReadingAidsPanel>
            )}
            
            <ReadingAidsPanel>
              <AidTitle>👥 Key Characters</AidTitle>
              <CharacterList>
                {prominentCharacters.map(character => (
                  <CharacterItem 
                    key={character}
                    onClick={() => setInputValue(`Tell me about ${character}`)}
                  >
                    {character}
                  </CharacterItem>
                ))}
              </CharacterList>
            </ReadingAidsPanel>
            
            <ReadingAidsPanel>
              <AidTitle>🎯 Quick References</AidTitle>
              <CharacterList>
                <CharacterItem>Timeline of Events</CharacterItem>
                <CharacterItem>Map of Places</CharacterItem>
                <CharacterItem>French Terms Glossary</CharacterItem>
                <CharacterItem>Family Trees</CharacterItem>
              </CharacterList>
            </ReadingAidsPanel>
          </SidebarContent>
        </Sidebar>

        <MainArea>
          <Header>
            <ModeIndicator>
              <span style={{ fontSize: '1.5rem' }}>{getModeDisplay().icon}</span>
              <span>{getModeDisplay().label}</span>
            </ModeIndicator>
            
            {mode === 'guided_journey' && (
              <button
                onClick={() => setShowJourneyMap(!showJourneyMap)}
                style={{
                  background: 'none',
                  border: `1px solid ${theme.colors.primary}`,
                  borderRadius: '8px',
                  padding: '0.5rem 1rem',
                  cursor: 'pointer'
                }}
              >
                {showJourneyMap ? 'Hide' : 'Show'} Journey Map
              </button>
            )}
          </Header>

          <ContentArea>
            <JourneyMapContainer isVisible={showJourneyMap}>
              <JourneyMap 
                currentVolume={currentVolume}
                onVolumeClick={setCurrentVolume}
              />
            </JourneyMapContainer>

            <MessagesContainer>
              {messages.map(message => (
                <Message key={message.id} isUser={message.isUser}>
                  <Avatar isUser={message.isUser}>
                    {message.isUser ? 'U' : 'P'}
                  </Avatar>
                  <MessageContent isUser={message.isUser}>
                    {message.passages ? (
                      message.passages.map((passage, idx) => (
                        <EnhancedPassageDisplay
                          key={idx}
                          passage={{
                            text: passage.text,
                            volume: "Swann's Way",
                            volumeNumber: 1,
                            chapter: "Combray",
                            page: passage.page || 1,
                            narrativeContext: "Early memories of childhood in Combray",
                            characters: ["Marcel", "Mother", "Grandmother"],
                            themes: [
                              { name: "Memory", color: "#7a9cc6" },
                              { name: "Time", color: "#e8b04b" }
                            ],
                            literaryDevices: ["Metaphor", "Stream of consciousness"],
                            relatedPassages: [],
                            readingTime: 3
                          }}
                          searchTerms={[]}
                        />
                      ))
                    ) : (
                      <p>{message.text}</p>
                    )}
                  </MessageContent>
                </Message>
              ))}
              
              {isLoading && (
                <Message isUser={false}>
                  <Avatar isUser={false}>P</Avatar>
                  <MessageContent isUser={false}>
                    <LoadingDots />
                  </MessageContent>
                </Message>
              )}
              
              <div ref={messagesEndRef} />
            </MessagesContainer>
          </ContentArea>

          <InputContainer>
            <QuickActions>
              {quickActions[mode]?.map(action => (
                <QuickActionButton
                  key={action}
                  onClick={() => setInputValue(action)}
                >
                  {action}
                </QuickActionButton>
              ))}
            </QuickActions>
            
            <InputWrapper>
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSubmit()}
                placeholder={`Ask about ${getModeDisplay().label.toLowerCase()}...`}
              />
              <SubmitButton onClick={handleSubmit} disabled={isLoading}>
                Send
              </SubmitButton>
            </InputWrapper>
          </InputContainer>
        </MainArea>
      </ChatContainer>
    </>
  );
};

export default ChatPageRedesigned;