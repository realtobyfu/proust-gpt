import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import PassageDisplay from './components/PassageDisplay';
import { useStreamingQuery, Passage } from './hooks/useStreamingQuery';

const ChatContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: #f7f4f0;
`;

const Sidebar = styled.div<{ $isOpen: boolean }>`
  width: ${props => props.$isOpen ? '250px' : '0'};
  background-color: #fff;
  border-right: ${props => props.$isOpen ? '1px solid #ccc' : 'none'};
  padding: ${props => props.$isOpen ? '2rem' : '0'};
  box-sizing: border-box;
  color: #333;
  overflow: hidden;
  transition: all 0.3s ease;
`;

const ChatArea = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  color: #333;
`;

const Header = styled.div`
  background-color: #fff;
  border-bottom: 1px solid #ccc;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const Breadcrumb = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  color: #666;

  a {
    color: #8b4513;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
`;

const ContextBar = styled.div<{ $visible: boolean }>`
  background-color: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid #e0e0e0;
  padding: ${props => props.$visible ? '1rem 2rem' : '0'};
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  color: #666;
  height: ${props => props.$visible ? 'auto' : '0'};
  overflow: hidden;
  transition: all 0.3s ease;
`;

const ProgressLine = styled.div`
  height: 2px;
  background-color: #e0e0e0;
  margin: 0.5rem 0;
  position: relative;

  &::after {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: 15%; // Example progress
    background-color: #8b4513;
  }
`;

const MessagesArea = styled.div`
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
`;

const MessageBubble = styled.div<{ $isUser: boolean }>`
  background-color: rgba(255, 255, 255, 0.6);
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  max-width: ${props => props.$isUser ? '60%' : '80%'};
  align-self: ${props => props.$isUser ? 'flex-start' : 'flex-end'};
  font-family: 'Georgia', serif;
  line-height: 1.6;
`;

const StreamingBubble = styled(MessageBubble)`
  white-space: pre-wrap;
`;

const blink = keyframes`
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
`;

const StreamingCursor = styled.span`
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: #8b4513;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: ${blink} 1s infinite;
`;

const InputArea = styled.div`
  background-color: #fff;
  border-top: 1px solid #ccc;
  padding: 1.5rem 2rem;
`;

const InputWrapper = styled.div`
  display: flex;
  align-items: center;
  position: relative;
  max-width: 800px;
  margin: 0 auto;
`;

const Input = styled.input`
  width: 100%;
  padding: 1rem;
  border: 1px solid #ccc;
  border-radius: 20px;
  font-size: 1rem;
  color: #333;
  background-color: #fff;
  font-family: 'Georgia', serif;

  &:focus {
    outline: none;
    border-color: #8b4513;
  }
`;

const SendButton = styled.button`
  position: absolute;
  right: 10px;
  background: none;
  border: none;
  color: #8b4513;
  cursor: pointer;
  font-size: 1rem;
  padding: 0.5rem;

  &:hover {
    color: #6b3410;
  }
`;

const StopButton = styled.button`
  background-color: #8b4513;
  color: white;
  border: none;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  cursor: pointer;
  margin-left: 0.5rem;

  &:hover {
    background-color: #6b3410;
  }
`;

const LoadingIndicator = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  color: #8b4513;
  text-align: center;
  margin: 1rem 0;
`;

const ToggleButton = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  cursor: pointer;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  text-decoration: underline;

  &:hover {
    color: #6b3410;
  }
`;

const SidebarSection = styled.div`
  margin-bottom: 2rem;
`;

const SidebarTitle = styled.h3`
  font-family: 'IBM Plex Sans', serif;
  font-size: 1rem;
  margin-bottom: 0.5rem;
  color: #333;
`;

const SidebarList = styled.ul`
  list-style: none;
  padding: 0;
  margin: 0;
`;

const SidebarItem = styled.li`
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  padding: 0.25rem 0;
  color: #666;
  cursor: pointer;
  transition: color 0.2s ease;

  &:hover {
    color: #8b4513;
  }
`;

const ErrorMessage = styled.div`
  background-color: #fff3f3;
  border: 1px solid #ffcdd2;
  color: #c62828;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
`;

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  passages?: Passage[];
}

const ChatPage: React.FC = () => {
  const location = useLocation();
  const { mode, prompt } = location.state || { mode: 'explore_lost_time', prompt: '' };
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [showContext, setShowContext] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [bookmarks, setBookmarks] = useState<string[]>([]);

  // Use streaming query hook
  const {
    response: streamingResponse,
    passages: streamingPassages,
    isLoading,
    isStreaming,
    error,
    query: streamQuery,
    abort,
    reset: resetStream,
  } = useStreamingQuery({ fallbackToNonStreaming: true });

  // Process initial prompt
  useEffect(() => {
    if (prompt) {
      handleSendMessage(prompt);
    }
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingResponse]);

  // When streaming completes, add the response as a message
  useEffect(() => {
    if (!isLoading && !isStreaming && streamingResponse) {
      const aiMessage: Message = {
        id: Date.now().toString(),
        text: streamingResponse,
        isUser: false,
        passages: streamingPassages.length > 0 ? streamingPassages : undefined,
      };
      setMessages(prev => [...prev, aiMessage]);
      resetStream();
    }
  }, [isLoading, isStreaming, streamingResponse, streamingPassages, resetStream]);

  const getModeDisplay = () => {
    switch (mode) {
      case 'explore_lost_time':
        return 'Exploring In Search of Lost Time';
      case 'refine_prose':
        return 'Reflecting in Proust\'s Style';
      default:
        return 'Reading Proust';
    }
  };

  const handleSendMessage = async (message: string = userInput) => {
    if (!message.trim() || isLoading) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      text: message,
      isUser: true
    };

    setMessages(prev => [...prev, newMessage]);
    setUserInput('');

    // Determine query mode
    const queryMode = mode === 'refine_prose' ? 'reflect' : 'explore';

    // Start streaming query
    await streamQuery(message, queryMode);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      handleSendMessage();
    }
  };

  const handleStopGenerating = () => {
    abort();
    // Add partial response as message if there's content
    if (streamingResponse) {
      const partialMessage: Message = {
        id: Date.now().toString(),
        text: streamingResponse + ' [stopped]',
        isUser: false,
      };
      setMessages(prev => [...prev, partialMessage]);
      resetStream();
    }
  };

  const handleBookmark = (passageText: string) => {
    setBookmarks(prev => [...prev, passageText]);
  };

  const characters = [
    'Marcel (Narrator)',
    'Swann',
    'Odette',
    'Gilberte',
    'Albertine',
    'Baron de Charlus',
    'Mme de Guermantes'
  ];

  return (
    <ChatContainer>
      <Sidebar $isOpen={sidebarOpen}>
        <SidebarSection>
          <SidebarTitle>Characters</SidebarTitle>
          <SidebarList>
            {characters.map(char => (
              <SidebarItem
                key={char}
                onClick={() => setUserInput(`Tell me about ${char}`)}
              >
                {char}
              </SidebarItem>
            ))}
          </SidebarList>
        </SidebarSection>

        <SidebarSection>
          <SidebarTitle>Reading Notes</SidebarTitle>
          <SidebarList>
            <SidebarItem>Timeline</SidebarItem>
            <SidebarItem>Places</SidebarItem>
            <SidebarItem>Your bookmarks ({bookmarks.length})</SidebarItem>
          </SidebarList>
        </SidebarSection>
      </Sidebar>

      <ChatArea>
        <Header>
          <Breadcrumb>
            <a href="/">Proust GPT</a> &gt; {getModeDisplay()}
          </Breadcrumb>
          <div>
            <ToggleButton onClick={() => setShowContext(!showContext)}>
              {showContext ? 'Hide' : 'Where am I?'}
            </ToggleButton>
            <span style={{ margin: '0 1rem' }}>|</span>
            <ToggleButton onClick={() => setSidebarOpen(!sidebarOpen)}>
              {sidebarOpen ? 'Hide' : 'Show'} reading notes
            </ToggleButton>
          </div>
        </Header>

        <ContextBar $visible={showContext}>
          <div>Current location: Volume I: Swann's Way, Part 1: Combray</div>
          <ProgressLine />
          <div>Progress: Beginning your journey through Proust</div>
        </ContextBar>

        <MessagesArea>
          {messages.map(message => (
            message.passages && message.passages.length > 0 ? (
              <div key={message.id}>
                {message.text && (
                  <MessageBubble $isUser={false}>
                    {message.text}
                  </MessageBubble>
                )}
                <div style={{ alignSelf: 'flex-end', maxWidth: '80%' }}>
                  {message.passages.map((passage: Passage, idx: number) => (
                    <PassageDisplay
                      key={idx}
                      text={passage.text}
                      volume={passage.book || "Swann's Way"}
                      page={passage.index}
                      narrativeContext={`From ${passage.chapter || 'Unknown chapter'}`}
                      characters={['Marcel', 'Mother', 'Grandmother']}
                      onBookmark={() => handleBookmark(passage.text)}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <MessageBubble key={message.id} $isUser={message.isUser}>
                {message.text}
              </MessageBubble>
            )
          ))}

          {/* Show streaming response */}
          {isStreaming && streamingResponse && (
            <StreamingBubble $isUser={false}>
              {streamingResponse}
              <StreamingCursor />
            </StreamingBubble>
          )}

          {/* Show error if any */}
          {error && (
            <ErrorMessage>
              Error: {error}
            </ErrorMessage>
          )}

          {isLoading && !isStreaming && (
            <LoadingIndicator>Searching through Proust's work...</LoadingIndicator>
          )}

          <div ref={messagesEndRef} />
        </MessagesArea>

        <InputArea>
          <InputWrapper>
            <Input
              type="text"
              placeholder="Ask about Proust..."
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
            {isStreaming ? (
              <StopButton onClick={handleStopGenerating}>
                Stop
              </StopButton>
            ) : (
              <SendButton onClick={() => handleSendMessage()} disabled={isLoading}>
                Send
              </SendButton>
            )}
          </InputWrapper>
        </InputArea>
      </ChatArea>
    </ChatContainer>
  );
};

export default ChatPage;
