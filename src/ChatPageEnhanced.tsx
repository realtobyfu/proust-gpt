import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import styled, { createGlobalStyle } from 'styled-components';
import LoadingDots from './components/LoadingDots';
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

const ChatContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: ${theme.colors.background};
  position: relative;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    flex-direction: column;
  }
`;

const Sidebar = styled.div<{ isOpen: boolean }>`
  width: 280px;
  background-color: ${theme.colors.white};
  border-right: 1px solid ${theme.colors.border};
  padding: 2rem;
  box-sizing: border-box;
  color: ${theme.colors.text};
  transition: transform ${theme.transitions.default};
  overflow-y: auto;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    position: fixed;
    left: 0;
    top: 0;
    height: 100%;
    transform: translateX(${props => props.isOpen ? '0' : '-100%'});
    z-index: 100;
    box-shadow: ${props => props.isOpen ? '2px 0 10px rgba(0,0,0,0.1)' : 'none'};
  }
`;

const MobileMenuToggle = styled.button`
  display: none;
  position: fixed;
  top: 1rem;
  left: 1rem;
  z-index: 101;
  background: ${theme.colors.white};
  border: 1px solid ${theme.colors.border};
  border-radius: 8px;
  padding: 0.5rem;
  cursor: pointer;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    display: block;
  }
`;

const ChatArea = styled.div`
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
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    padding: 1rem 1rem 1rem 4rem;
  }
`;

const ChatMode = styled.div`
  font-family: ${theme.fonts.secondary};
  font-size: 1.1rem;
  font-weight: 500;
  color: ${theme.colors.text};
`;

const HeaderActions = styled.div`
  display: flex;
  gap: 1rem;
`;

const ActionButton = styled.button`
  background: none;
  border: 1px solid ${theme.colors.border};
  border-radius: 6px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font-family: ${theme.fonts.secondary};
  color: ${theme.colors.text};
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: ${theme.colors.secondary};
    border-color: ${theme.colors.primary};
  }
`;

const MessagesContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    padding: 1rem;
  }
`;

const MessageWrapper = styled.div<{ isUser: boolean }>`
  display: flex;
  flex-direction: column;
  align-items: ${props => props.isUser ? 'flex-start' : 'flex-end'};
  max-width: 70%;
  align-self: ${props => props.isUser ? 'flex-start' : 'flex-end'};
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    max-width: 90%;
  }
`;

const MessageBubble = styled.div<{ isUser: boolean }>`
  background-color: ${props => props.isUser ? theme.colors.userMessageBg : theme.colors.proustMessageBg};
  border-radius: 16px;
  padding: 1rem 1.5rem;
  box-shadow: 0 2px 8px ${theme.colors.shadow};
  position: relative;
  animation: fadeIn 0.3s ease;
  
  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const MessageText = styled.p`
  margin: 0;
  line-height: 1.6;
  color: ${theme.colors.text};
  
  /* Support for markdown-style formatting */
  em {
    font-style: italic;
    color: ${theme.colors.textLight};
  }
  
  strong {
    font-weight: 600;
  }
`;

const MessageMeta = styled.div`
  font-size: 0.85rem;
  color: ${theme.colors.textLight};
  margin-top: 0.5rem;
  font-style: italic;
`;

const MessageTime = styled.span`
  font-size: 0.75rem;
  color: ${theme.colors.textLight};
  margin-top: 0.25rem;
`;

const InputContainer = styled.div`
  background: ${theme.colors.white};
  border-top: 1px solid ${theme.colors.border};
  padding: 1.5rem 2rem;
  
  @media (max-width: ${theme.breakpoints.mobile}) {
    padding: 1rem;
  }
`;

const InputWrapper = styled.form`
  display: flex;
  gap: 1rem;
  align-items: center;
`;

const Input = styled.input`
  flex: 1;
  padding: 0.75rem 1.25rem;
  border: 1px solid ${theme.colors.border};
  border-radius: 24px;
  font-size: 1rem;
  font-family: ${theme.fonts.primary};
  color: ${theme.colors.text};
  background-color: ${theme.colors.secondary};
  transition: all ${theme.transitions.default};
  
  &:focus {
    outline: none;
    border-color: ${theme.colors.primary};
    background-color: ${theme.colors.white};
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const SendButton = styled.button`
  padding: 0.75rem 1.5rem;
  background-color: ${theme.colors.primary};
  color: ${theme.colors.white};
  border: none;
  border-radius: 24px;
  font-family: ${theme.fonts.secondary};
  font-weight: 500;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover:not(:disabled) {
    background-color: #6b3410;
    transform: translateY(-1px);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const ConversationList = styled.div`
  margin-top: 2rem;
`;

const ConversationItem = styled.div`
  padding: 1rem;
  margin-bottom: 0.5rem;
  background: ${theme.colors.secondary};
  border-radius: 8px;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: ${theme.colors.messageBg};
    transform: translateX(4px);
  }
`;

const ConversationTitle = styled.h4`
  margin: 0 0 0.25rem 0;
  font-size: 0.95rem;
  font-weight: 500;
`;

const ConversationDate = styled.p`
  margin: 0;
  font-size: 0.85rem;
  color: ${theme.colors.textLight};
`;

interface Message {
  text: string;
  isUser: boolean;
  book?: string;
  chapter?: string;
  timestamp: Date;
}

const ChatPageEnhanced: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { mode, prompt } = location.state || { mode: 'explore_lost_time', prompt: '' };

  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [initialPromptSent, setInitialPromptSent] = useState<boolean>(false);

  const getModeDisplayString = (mode: string) => {
    switch (mode) {
      case 'explore_lost_time':
        return 'Explore In Search of Lost Time';
      case 'refine_prose':
        return 'Reflect on Your Day';
      default:
        return 'Explore In Search of Lost Time';
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (prompt && prompt.trim() !== '' && !initialPromptSent) {
      setMessages([{ 
        text: prompt, 
        isUser: true, 
        timestamp: new Date() 
      }]);
      setIsLoading(true);
      sendMessageToBackend(prompt);
      setInitialPromptSent(true);
    }
  }, [prompt, initialPromptSent]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (userInput.trim() === '' || isLoading) return;

    const newMessage: Message = {
      text: userInput,
      isUser: true,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, newMessage]);
    setIsLoading(true);
    sendMessageToBackend(userInput);
    setUserInput('');
  };

  const sendMessageToBackend = async (message: string) => {
    let apiEndpoint = '';

    switch (mode) {
      case 'explore_lost_time':
        apiEndpoint = 'http://127.0.0.1:5000/api/explore_lost_time';
        break;
      case 'refine_prose':
        apiEndpoint = 'http://127.0.0.1:5000/api/reflect';
        break;
      default:
        apiEndpoint = 'http://127.0.0.1:5000/api/explore_lost_time';
    }

    try {
      const response = await fetch(apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (mode === 'explore_lost_time' && data.passages) {
        const newMessages = data.passages.map((passage: any) => ({
          text: passage.text,
          isUser: false,
          book: passage.book,
          chapter: passage.chapter,
          timestamp: new Date()
        }));
        setMessages(prev => [...prev, ...newMessages]);
      } else if (mode === 'refine_prose' && data.reply) {
        setMessages(prev => [...prev, {
          text: data.reply,
          isUser: false,
          timestamp: new Date()
        }]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        text: 'I apologize, but I encountered an error processing your message. Please try again.',
        isUser: false,
        timestamp: new Date()
      }]);
    }

    setIsLoading(false);
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      hour12: true 
    });
  };

  const handleNewChat = () => {
    setMessages([]);
    setUserInput('');
    navigate('/');
  };

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <>
      <GlobalStyle />
      <ChatContainer>
        <MobileMenuToggle onClick={toggleSidebar}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M3 12h18M3 6h18M3 18h18" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </MobileMenuToggle>

        <Sidebar isOpen={isSidebarOpen}>
          <h3>Past Conversations</h3>
          <ConversationList>
            <ConversationItem>
              <ConversationTitle>About Combray</ConversationTitle>
              <ConversationDate>Yesterday, 3:42 PM</ConversationDate>
            </ConversationItem>
            <ConversationItem>
              <ConversationTitle>Memory and Time</ConversationTitle>
              <ConversationDate>Dec 15, 2:15 PM</ConversationDate>
            </ConversationItem>
            <ConversationItem>
              <ConversationTitle>Reflections on Sunday</ConversationTitle>
              <ConversationDate>Dec 14, 5:30 PM</ConversationDate>
            </ConversationItem>
          </ConversationList>
        </Sidebar>

        <ChatArea>
          <Header>
            <ChatMode>{getModeDisplayString(mode)}</ChatMode>
            <HeaderActions>
              <ActionButton onClick={handleNewChat}>New Chat</ActionButton>
            </HeaderActions>
          </Header>

          <MessagesContainer>
            {messages.map((msg, index) => (
              <MessageWrapper key={index} isUser={msg.isUser}>
                <MessageBubble isUser={msg.isUser}>
                  <MessageText>{msg.text}</MessageText>
                  {!msg.isUser && msg.book && (
                    <MessageMeta>
                      {msg.book}, {msg.chapter}
                    </MessageMeta>
                  )}
                </MessageBubble>
                <MessageTime>{formatTime(msg.timestamp)}</MessageTime>
              </MessageWrapper>
            ))}
            {isLoading && (
              <MessageWrapper isUser={false}>
                <MessageBubble isUser={false}>
                  <LoadingDots />
                </MessageBubble>
              </MessageWrapper>
            )}
            <div ref={messagesEndRef} />
          </MessagesContainer>

          <InputContainer>
            <InputWrapper onSubmit={handleSubmit}>
              <Input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder="Type your message here..."
                disabled={isLoading}
              />
              <SendButton type="submit" disabled={isLoading || !userInput.trim()}>
                Send
              </SendButton>
            </InputWrapper>
          </InputContainer>
        </ChatArea>
      </ChatContainer>
    </>
  );
};

export default ChatPageEnhanced;