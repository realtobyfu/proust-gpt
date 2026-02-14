import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import PassageDisplay from './components/PassageDisplay';
import PassageLightbox from './components/PassageLightbox';
import MarkdownMessage from './components/MarkdownMessage';
import { useStreamingQuery, Passage } from './hooks/useStreamingQuery';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useChatSessions, Message } from './hooks/useChatSessions';

const ChatContainer = styled.div`
  display: flex;
  width: 100%;
  height: 100vh;
  background-color: #f7f4f0;
`;

const Sidebar = styled.div<{ $isOpen: boolean }>`
  width: ${props => props.$isOpen ? '250px' : '0'};
  background-color: #faf8f5;
  border-right: ${props => props.$isOpen ? '1px solid #e0d8cf' : 'none'};
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
  background-color: #faf8f5;
  border-bottom: 1px solid #e0d8cf;
  padding: 1.25rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const BackButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: rgba(139, 69, 19, 0.05);
  //border: 1px solid #d4ccc3;
  border-radius: 20px;
  padding: 0.4rem 1rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #8b4513;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.1);
    border-color: #8b4513;
  }
`;

const ModeLabel = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.95rem;
  color: #666;
  font-weight: 500;
`;

const ContextBar = styled.div<{ $visible: boolean }>`
  background-color: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid #e0e0e0;
  padding: ${props => props.$visible ? '0.6rem 2rem' : '0 2rem'};
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.85rem;
  color: #666;
  max-height: ${props => props.$visible ? '80px' : '0'};
  overflow: hidden;
  transition: all 0.3s ease;
`;

const ProgressLine = styled.div<{ $progress: number }>`
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
    width: ${props => props.$progress}%;
    background-color: #8b4513;
    transition: width 0.3s ease;
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
  background-color: ${props => props.$isUser ? '#6b3410' : '#f0ebe4'};
  border-radius: ${props => props.$isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px'};
  border: ${props => props.$isUser ? 'none' : '1px solid #e0d8cf'};
  border-left: ${props => !props.$isUser ? '3px solid #8b4513' : undefined};
  color: ${props => props.$isUser ? '#fff' : '#3a3a3a'};
  padding: 1rem;
  margin-bottom: 1rem;
  max-width: ${props => props.$isUser ? '60%' : '80%'};
  align-self: ${props => props.$isUser ? 'flex-end' : 'flex-start'};
  font-family: 'Georgia', serif;
  line-height: 1.6;
`;

const StreamingBubble = styled(MessageBubble)``;

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
  background-color: #faf8f5;
  border-top: 1px solid #e0d8cf;
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
  padding-right: 3rem;
  border: 1px solid #d4ccc3;
  border-radius: 20px;
  font-size: 1rem;
  color: #333;
  background-color: #fff;
  font-family: 'Georgia', serif;

  &::placeholder {
    color: #a89888;
  }

  &:focus {
    outline: none;
    border-color: #8b4513;
    box-shadow: 0 0 0 3px rgba(139, 69, 19, 0.1);
  }
`;

const SendButton = styled.button`
  position: absolute;
  right: 10px;
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

  &:disabled {
    background-color: #ccc;
    cursor: default;
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

const HamburgerButton = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  cursor: pointer;
  padding: 0.3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: color 0.2s ease;

  &:hover {
    color: #6b3410;
  }
`;

const ToggleButton = styled.button`
  background: rgba(139, 69, 19, 0.06);
  border: none;
  border-radius: 16px;
  padding: 0.4rem 0.9rem;
  color: #8b4513;
  cursor: pointer;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.12);
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
  background-color: #fdf6f0;
  border: 1px solid #e0c8b0;
  color: #8b4513;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  max-width: 80%;
  align-self: flex-start;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;

  &::before {
    content: '\26A0  ';
  }
`;

const NewChatButton = styled.button`
  width: 100%;
  padding: 0.45rem 0;
  background: rgba(139, 69, 19, 0.08);
  border: 1px dashed #c4a882;
  border-radius: 8px;
  color: #8b4513;
  font-size: 1.3rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.15);
  }
`;

const SessionItem = styled.div<{ $active: boolean }>`
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  background: ${props => props.$active ? 'rgba(139, 69, 19, 0.1)' : 'transparent'};
  border-left: ${props => props.$active ? '3px solid #8b4513' : '3px solid transparent'};
  margin-bottom: 0.25rem;
  position: relative;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.06);
  }

  &:hover .delete-btn {
    opacity: 1;
  }
`;

const SessionTitle = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.82rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 1.2rem;
`;

const SessionMeta = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.7rem;
  color: #999;
  margin-top: 0.15rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
`;

const SessionModeTag = styled.span<{ $mode: string }>`
  font-size: 0.65rem;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
  background: ${props => props.$mode === 'refine_prose' ? 'rgba(90, 120, 160, 0.12)' : 'rgba(139, 69, 19, 0.08)'};
  color: ${props => props.$mode === 'refine_prose' ? '#5a78a0' : '#8b4513'};
`;

const DeleteButton = styled.button`
  position: absolute;
  top: 0.45rem;
  right: 0.3rem;
  background: none;
  border: none;
  color: #c4a882;
  cursor: pointer;
  font-size: 0.9rem;
  line-height: 1;
  padding: 0.1rem 0.25rem;
  border-radius: 3px;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;

  &:hover {
    color: #a03030;
    background: rgba(160, 48, 48, 0.08);
  }
`;

const EmptyState = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.2rem;
`;

const EmptyStateTitle = styled.h2`
  font-family: 'Belgrano', serif;
  font-weight: 400;
  font-size: 1.3rem;
  color: #8b4513;
  margin: 0;
`;

const SuggestionChips = styled.div`
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  justify-content: center;
`;

const SuggestionChip = styled.button`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #6b3410;
  background: rgba(139, 69, 19, 0.06);
  border: 1px solid #d4ccc3;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.12);
    border-color: #8b4513;
  }
`;

interface Bookmark {
  id: string;
  text: string;
  book: string;
  chapter: string;
  index?: number;
  savedAt: string;
}

interface LastPassagePosition {
  book: string;
  chapter: string;
  index?: number;
}

const ChatPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { mode: locationMode, prompt } = location.state || { mode: 'explore_lost_time', prompt: '' };
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [showContext, setShowContext] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState<string>(locationMode || 'explore_lost_time');
  const [bookmarks, setBookmarks] = useLocalStorage<Bookmark[]>('proust-bookmarks', []);
  const [lastPosition, setLastPosition] = useLocalStorage<LastPassagePosition | null>('proust-last-position', null);

  // Lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxPassages, setLightboxPassages] = useState<Passage[]>([]);
  const [lightboxInitialIndex, setLightboxInitialIndex] = useState(0);

  // Session management
  const {
    sessions,
    createSession,
    saveSession,
    loadSession,
    deleteSession,
    getMostRecentSession,
  } = useChatSessions();

  const currentSessionIdRef = useRef<string | null>(null);

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

  // Session-aware initialization
  useEffect(() => {
    if (prompt) {
      // New conversation from landing page with a prompt
      const session = createSession(locationMode || 'explore_lost_time');
      currentSessionIdRef.current = session.id;
      setActiveMode(locationMode || 'explore_lost_time');
      // Clear location state so refresh doesn't re-trigger
      navigate(location.pathname, { replace: true, state: {} });
      handleSendMessage(prompt);
    } else {
      // No prompt — always start a new empty session
      const mode = locationMode || 'explore_lost_time';
      const session = createSession(mode);
      currentSessionIdRef.current = session.id;
      setActiveMode(mode);
    }
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingResponse]);

  // Auto-save messages to session
  useEffect(() => {
    if (currentSessionIdRef.current && messages.length > 0) {
      saveSession(currentSessionIdRef.current, messages, activeMode);
    }
  }, [messages, activeMode, saveSession]);

  // Session handlers
  const handleSelectSession = useCallback((id: string) => {
    if (id === currentSessionIdRef.current) return;
    // Save current session first
    if (currentSessionIdRef.current && messages.length > 0) {
      saveSession(currentSessionIdRef.current, messages, activeMode);
    }
    const session = loadSession(id);
    if (session) {
      currentSessionIdRef.current = session.id;
      setMessages(session.messages);
      setActiveMode(session.mode);
      resetStream();
    }
  }, [messages, activeMode, saveSession, loadSession, resetStream]);

  const handleNewConversation = useCallback(() => {
    // Save current session
    if (currentSessionIdRef.current && messages.length > 0) {
      saveSession(currentSessionIdRef.current, messages, activeMode);
    }
    const session = createSession(activeMode);
    currentSessionIdRef.current = session.id;
    setMessages([]);
    resetStream();
  }, [messages, activeMode, saveSession, createSession, resetStream]);

  const handleDeleteSession = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteSession(id);
    if (id === currentSessionIdRef.current) {
      // Deleted current session — load most recent or create new
      const recent = getMostRecentSession();
      if (recent && recent.messages.length > 0) {
        currentSessionIdRef.current = recent.id;
        setMessages(recent.messages);
        setActiveMode(recent.mode);
        loadSession(recent.id);
      } else {
        const session = createSession(activeMode);
        currentSessionIdRef.current = session.id;
        setMessages([]);
      }
      resetStream();
    }
  }, [deleteSession, getMostRecentSession, loadSession, createSession, activeMode, resetStream]);

  // When streaming completes, add the response as a message and track position
  useEffect(() => {
    if (!isLoading && !isStreaming && streamingResponse) {
      const aiMessage: Message = {
        id: Date.now().toString(),
        text: streamingResponse,
        isUser: false,
        passages: streamingPassages.length > 0 ? streamingPassages : undefined,
      };
      setMessages(prev => [...prev, aiMessage]);

      // Track last passage position
      if (streamingPassages.length > 0) {
        const lastPassage = streamingPassages[streamingPassages.length - 1];
        setLastPosition({
          book: lastPassage.book || "Unknown",
          chapter: lastPassage.chapter || "Unknown",
          index: lastPassage.index,
        });
      }

      resetStream();
    }
  }, [isLoading, isStreaming, streamingResponse, streamingPassages, resetStream]);

  const getModeDisplay = () => {
    switch (activeMode) {
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
    const queryMode = activeMode === 'refine_prose' ? 'reflect' : 'explore';

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

  const handleBookmark = (passage: Passage) => {
    const existing = bookmarks.find(b => b.text === passage.text);
    if (existing) {
      // Remove bookmark (toggle off)
      setBookmarks(bookmarks.filter(b => b.text !== passage.text));
    } else {
      // Add bookmark
      setBookmarks([...bookmarks, {
        id: Date.now().toString(),
        text: passage.text,
        book: passage.book || "Unknown",
        chapter: passage.chapter || "Unknown",
        index: passage.index,
        savedAt: new Date().toISOString(),
      }]);
    }
  };

  const isBookmarked = (passageText: string) => {
    return bookmarks.some(b => b.text === passageText);
  };

  const handleReadInContext = useCallback(async (passage: Passage) => {
    if (passage.index == null) return;
    try {
      const res = await fetch(`http://127.0.0.1:5000/api/read/locate?index=${passage.index}`);
      const data = await res.json();
      if (data.error) {
        console.error('Failed to locate passage:', data.error);
        return;
      }
      const params = new URLSearchParams({
        volume: data.volume.toString(),
        chapter: data.chapter,
        page: data.page.toString(),
        passageIndex: data.passageIndex.toString(),
      });
      navigate(`/read?${params}`);
    } catch (err) {
      console.error('Failed to locate passage:', err);
    }
  }, [navigate]);

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
          <NewChatButton onClick={handleNewConversation} title="New conversation">
            +
          </NewChatButton>
          <SidebarTitle>Conversations</SidebarTitle>
          {sessions.length === 0 ? (
            <SidebarItem style={{ color: '#aaa', cursor: 'default' }}>
              No conversations yet
            </SidebarItem>
          ) : (
            sessions.map(s => (
              <SessionItem
                key={s.id}
                $active={s.id === currentSessionIdRef.current}
                onClick={() => handleSelectSession(s.id)}
              >
                <SessionTitle>{s.title}</SessionTitle>
                <SessionMeta>
                  <SessionModeTag $mode={s.mode}>
                    {s.mode === 'refine_prose' ? 'Reflect' : 'Explore'}
                  </SessionModeTag>
                  {new Date(s.updatedAt).toLocaleDateString()}
                </SessionMeta>
                <DeleteButton
                  className="delete-btn"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  title="Delete conversation"
                >
                  &times;
                </DeleteButton>
              </SessionItem>
            ))
          )}
        </SidebarSection>

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
          <SidebarTitle>Bookmarks ({bookmarks.length})</SidebarTitle>
          <SidebarList>
            {bookmarks.length === 0 ? (
              <SidebarItem style={{ color: '#aaa', cursor: 'default' }}>
                No bookmarks yet
              </SidebarItem>
            ) : (
              bookmarks.map(bm => (
                <SidebarItem
                  key={bm.id}
                  onClick={() => setUserInput(`Tell me more about this passage: "${bm.text.slice(0, 80)}..."`)}
                  title={bm.text.slice(0, 200)}
                >
                  {bm.book} &mdash; {bm.text.slice(0, 40)}...
                </SidebarItem>
              ))
            )}
          </SidebarList>
        </SidebarSection>
      </Sidebar>

      <ChatArea>
        <Header>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <HamburgerButton onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="6" x2="21" y2="6"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            </HamburgerButton>
            <BackButton onClick={() => navigate('/')}>&larr;</BackButton>
            <ModeLabel>{getModeDisplay()}</ModeLabel>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <ToggleButton onClick={() => setShowContext(!showContext)}>
              {showContext ? 'Hide' : 'Where am I?'}
            </ToggleButton>
            <Link to="/about" style={{ color: '#8b4513', fontFamily: "'IBM Plex Sans', serif", fontSize: '0.9rem', textDecoration: 'underline' }}>
              About
            </Link>
          </div>
        </Header>

        <ContextBar $visible={showContext}>
          {lastPosition ? (
            <>
              <div>Current location: {lastPosition.book}, {lastPosition.chapter}</div>
              <ProgressLine $progress={lastPosition.index != null ? Math.min(100, Number((lastPosition.index / 12764 * 100).toFixed(0))) : 0} />
              <div>Progress: {lastPosition.index != null ? `${Math.min(100, Number((lastPosition.index / 12764 * 100).toFixed(0)))}% through the text` : 'Position unknown'}</div>
            </>
          ) : (
            <div>Begin exploring to track your position</div>
          )}
        </ContextBar>

        <MessagesArea>
          {messages.length === 0 && !isLoading && !isStreaming && (
            <EmptyState>
              <EmptyStateTitle>
                {activeMode === 'refine_prose'
                  ? 'What moment would you like to reflect on?'
                  : 'What would you like to explore?'}
              </EmptyStateTitle>
              <SuggestionChips>
                {activeMode === 'refine_prose' ? (
                  <>
                    <SuggestionChip onClick={() => handleSendMessage('I had a quiet morning with coffee and sunlight')}>
                      A quiet morning
                    </SuggestionChip>
                    <SuggestionChip onClick={() => handleSendMessage('I ran into an old friend I hadn\'t seen in years')}>
                      An unexpected encounter
                    </SuggestionChip>
                    <SuggestionChip onClick={() => handleSendMessage('A familiar smell brought back a childhood memory')}>
                      A sudden memory
                    </SuggestionChip>
                  </>
                ) : (
                  <>
                    <SuggestionChip onClick={() => handleSendMessage('The madeleine scene')}>
                      The madeleine scene
                    </SuggestionChip>
                    <SuggestionChip onClick={() => handleSendMessage('Swann\'s jealousy over Odette')}>
                      Swann's jealousy
                    </SuggestionChip>
                    <SuggestionChip onClick={() => handleSendMessage('Time and memory in Proust')}>
                      Time and memory
                    </SuggestionChip>
                  </>
                )}
              </SuggestionChips>
            </EmptyState>
          )}

          {messages.map(message => (
            message.passages && message.passages.length > 0 ? (
              <div key={message.id}>
                {message.text && (
                  <MessageBubble $isUser={false}>
                    <MarkdownMessage content={message.text} />
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
                      onBookmark={() => handleBookmark(passage)}
                      isBookmarked={isBookmarked(passage.text)}
                      truncated
                      onClick={() => {
                        setLightboxPassages(message.passages!);
                        setLightboxInitialIndex(idx);
                        setLightboxOpen(true);
                      }}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <MessageBubble key={message.id} $isUser={message.isUser}>
                {message.isUser ? message.text : <MarkdownMessage content={message.text} />}
              </MessageBubble>
            )
          ))}

          {/* Show streaming response */}
          {isStreaming && streamingResponse && (
            <StreamingBubble $isUser={false}>
              <MarkdownMessage content={streamingResponse} />
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
              placeholder={activeMode === 'refine_prose' ? 'Share a moment from your day...' : 'Ask about a passage, character, or theme...'}
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
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </SendButton>
            )}
          </InputWrapper>
        </InputArea>
      </ChatArea>
      <PassageLightbox
        passages={lightboxPassages}
        initialIndex={lightboxInitialIndex}
        isOpen={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
        onBookmark={handleBookmark}
        isBookmarked={isBookmarked}
        onReadInContext={handleReadInContext}
      />
    </ChatContainer>
  );
};

export default ChatPage;
