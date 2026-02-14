import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import styled, { keyframes } from 'styled-components';
import PassageCard from './components/PassageCard';
import ReaderPanel from './components/ReaderPanel';
import MarkdownMessage from './components/MarkdownMessage';
import { useStreamingQuery, Passage } from './hooks/useStreamingQuery';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useChatSessions, Message } from './hooks/useChatSessions';

// ── Responsive hook ──────────────────────────────────────────────────────────

function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1025px)').matches
  );

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1025px)');
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return isDesktop;
}

// ── Styled Components ────────────────────────────────────────────────────────

const ChatContainer = styled.div`
  display: flex;
  width: 100vw;
  height: 100vh;
  background-color: #f7f4f0;
  overflow: hidden;
`;

const Sidebar = styled.div<{ $isOpen: boolean }>`
  width: ${props => props.$isOpen ? '250px' : '0'};
  background-color: #faf8f5;
  border-right: ${props => props.$isOpen ? '1px solid #e0d8cf' : 'none'};
  padding: ${props => props.$isOpen ? '2rem' : '0'};
  box-sizing: border-box;
  color: #333;
  overflow-x: hidden;
  overflow-y: ${props => props.$isOpen ? 'auto' : 'hidden'};
  scrollbar-width: none;
  &::-webkit-scrollbar { display: none; }
  transition: all 0.3s ease;
`;

const ChatContent = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;

  @media (min-width: 1025px) {
    flex-direction: row;
  }
`;

const ConversationPane = styled.div<{ $readerOpen: boolean; $splitPercent: number }>`
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: flex 0.3s ease;

  @media (min-width: 1025px) {
    flex: ${props => props.$readerOpen ? `0 0 ${props.$splitPercent}%` : '1'};
  }
`;

const Divider = styled.div`
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  flex-shrink: 0;

  &::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 2px;
    width: 2px;
    background: #e0d8cf;
    transition: background 0.15s;
  }

  &:hover::after {
    background: #8b4513;
  }
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
  border: none;
  border-radius: 20px;
  padding: 0.4rem 1rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #8b4513;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.1);
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
  font-family: 'IBM Plex Sans', sans-serif;
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

  &::-webkit-scrollbar {
    width: 5px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: #d4ccc3;
    border-radius: 3px;
  }
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

const SynthesisBanner = styled.div`
  border-left: 3px solid #c4a882;
  background: rgba(196, 168, 130, 0.08);
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  font-family: 'Georgia', serif;
  font-style: italic;
  font-size: 0.9rem;
  color: #555;
  line-height: 1.5;
  border-radius: 0 6px 6px 0;
  max-width: 80%;
  align-self: flex-start;
`;

const ResultsHeader = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #999;
  margin-bottom: 0.5rem;
  max-width: 80%;
  align-self: flex-start;
`;

const FloatingInputArea = styled.div`
  padding: 1rem 2rem 1.5rem;
  position: relative;
`;

const InputLabel = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.75rem;
  color: #a89888;
  margin-bottom: 0.4rem;
  padding-left: 1rem;
`;

const InputPill = styled.div`
  display: flex;
  align-items: center;
  position: relative;
  max-width: 800px;
  margin: 0 auto;
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

const Input = styled.input`
  width: 100%;
  padding: 0.9rem 1.2rem;
  padding-right: 3rem;
  border: none;
  border-radius: 24px;
  font-size: 1rem;
  color: #333;
  background: transparent;
  font-family: 'Georgia', serif;

  &::placeholder {
    color: #a89888;
  }

  &:focus {
    outline: none;
  }
`;

const SendButton = styled.button`
  position: absolute;
  right: 8px;
  width: 34px;
  height: 34px;
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
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  cursor: pointer;
  margin-right: 0.5rem;

  &:hover {
    background-color: #6b3410;
  }
`;

const LoadingIndicator = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
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
  font-family: 'IBM Plex Sans', sans-serif;
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
  font-family: 'IBM Plex Sans', sans-serif;
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
  font-family: 'IBM Plex Sans', sans-serif;
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
  font-family: 'IBM Plex Sans', sans-serif;
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
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 1.2rem;
`;

const SessionMeta = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
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
  color: #2a2a2a;
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
  color: #3a3028;
  background: rgba(58, 48, 40, 0.04);
  border: 1px solid #d4ccc3;
  border-radius: 20px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(58, 48, 40, 0.1);
    border-color: #564a40;
  }
`;

// ── Prompt pools ─────────────────────────────────────────────────────────────

const EXPLORE_PROMPTS = [
  'What is the madeleine scene really about?',
  "How does Swann's love for Odette change over time?",
  'Show me passages about falling asleep',
  'How does Proust explore the role of memory?',
  "What is the narrator's relationship with his grandmother?",
  'Tell me about the hawthorn flowers in Combray',
  "What are the two 'ways' at Combray?",
  'What is the magic lantern scene about?',
  'Describe the Guermantes salon',
  'Who is Baron de Charlus?',
  'How does Proust treat the passage of time?',
  'What role does reading play in the novel?',
];

const REFLECT_PROMPTS = [
  'A taste that brought back a forgotten place',
  'I noticed someone I love has changed',
  'I went back somewhere from my childhood',
  'The smell of someone who is gone',
  'Time passing in a single moment',
  'I noticed something beautiful in an ordinary moment',
  'A sound that took me to another time',
  'The feeling of waiting for something',
  'A familiar place that felt unfamiliar',
  'How much I have changed without noticing',
  'An unexpected moment of happiness',
  'The weight of past selves I carry',
];

function shuffleArray<T>(arr: T[]): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// ── Interfaces ───────────────────────────────────────────────────────────────

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

// ── Component ────────────────────────────────────────────────────────────────

const ChatPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { mode: locationMode, prompt } = location.state || { mode: 'explore_lost_time', prompt: '' };
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isDesktop = useIsDesktop();

  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [showContext, setShowContext] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState<string>(locationMode || 'explore_lost_time');
  const [bookmarks, setBookmarks] = useLocalStorage<Bookmark[]>('proust-bookmarks', []);
  const [lastPosition, setLastPosition] = useLocalStorage<LastPassagePosition | null>('proust-last-position', null);

  // Shuffled suggestion prompts
  const exploreSuggestions = useMemo(() => shuffleArray(EXPLORE_PROMPTS).slice(0, 3), []);
  const reflectSuggestions = useMemo(() => shuffleArray(REFLECT_PROMPTS).slice(0, 3), []);

  // Reader panel state (desktop only)
  const [selectedPassage, setSelectedPassage] = useState<Passage | null>(null);
  const [selectedPassageGroup, setSelectedPassageGroup] = useState<Passage[]>([]);

  // Draggable split state
  const [splitPercent, setSplitPercent] = useState(55);
  const chatContentRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

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
    metadata: streamingMetadata,
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
      const session = createSession(locationMode || 'explore_lost_time');
      currentSessionIdRef.current = session.id;
      setActiveMode(locationMode || 'explore_lost_time');
      navigate(location.pathname, { replace: true, state: {} });
      handleSendMessage(prompt);
    } else {
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

  const readerOpen = isDesktop && selectedPassage !== null;

  // Auto-open sidebar for returning users (desktop only)
  useEffect(() => {
    if (isDesktop && sessions.some(s => s.messageCount > 0)) {
      setSidebarOpen(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-collapse sidebar when reader panel opens
  useEffect(() => {
    if (readerOpen) {
      setSidebarOpen(false);
    }
  }, [readerOpen]);

  // Draggable divider handler
  const handleDividerMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !chatContentRef.current) return;
      const rect = chatContentRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(75, Math.max(30, pct)));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, []);

  // Session handlers
  const handleSelectSession = useCallback((id: string) => {
    if (id === currentSessionIdRef.current) return;
    if (currentSessionIdRef.current && messages.length > 0) {
      saveSession(currentSessionIdRef.current, messages, activeMode);
    }
    const session = loadSession(id);
    if (session) {
      currentSessionIdRef.current = session.id;
      setMessages(session.messages);
      setActiveMode(session.mode);
      resetStream();
      setSelectedPassage(null);
    }
  }, [messages, activeMode, saveSession, loadSession, resetStream]);

  const handleNewConversation = useCallback(() => {
    if (currentSessionIdRef.current && messages.length > 0) {
      saveSession(currentSessionIdRef.current, messages, activeMode);
    }
    const session = createSession(activeMode);
    currentSessionIdRef.current = session.id;
    setMessages([]);
    resetStream();
    setSelectedPassage(null);
  }, [messages, activeMode, saveSession, createSession, resetStream]);

  const handleDeleteSession = useCallback((e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteSession(id);
    if (id === currentSessionIdRef.current) {
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
      setSelectedPassage(null);
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
        metadata: streamingMetadata || undefined,
      };
      setMessages(prev => [...prev, aiMessage]);

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
  }, [isLoading, isStreaming, streamingResponse, streamingPassages, streamingMetadata, resetStream]);

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
    setSelectedPassage(null);

    const queryMode = activeMode === 'refine_prose' ? 'reflect' : 'explore';
    await streamQuery(message, queryMode);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      handleSendMessage();
    }
  };

  const handleStopGenerating = () => {
    abort();
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
      setBookmarks(bookmarks.filter(b => b.text !== passage.text));
    } else {
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

  const handleSelectPassageForReader = useCallback((passage: Passage, allPassages: Passage[]) => {
    setSelectedPassage(passage);
    setSelectedPassageGroup(allPassages);
  }, []);

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

      <ChatContent ref={chatContentRef}>
        <ConversationPane $readerOpen={readerOpen} $splitPercent={splitPercent}>
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
              <Link to="/about" style={{ color: '#8b4513', fontFamily: "'IBM Plex Sans', sans-serif", fontSize: '0.9rem', textDecoration: 'underline' }}>
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
                  {(activeMode === 'refine_prose' ? reflectSuggestions : exploreSuggestions).map((text, i) => (
                    <SuggestionChip key={i} onClick={() => handleSendMessage(text)}>
                      {text}
                    </SuggestionChip>
                  ))}
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

                  {message.metadata?.synthesis && (
                    <SynthesisBanner>{message.metadata.synthesis}</SynthesisBanner>
                  )}

                  <ResultsHeader>
                    {message.passages.length} passage{message.passages.length !== 1 ? 's' : ''} found
                  </ResultsHeader>

                  <div style={{ alignSelf: 'flex-start', maxWidth: '80%' }}>
                    <PassageCard
                      passages={message.passages}
                      onBookmark={handleBookmark}
                      isBookmarked={isBookmarked}
                      onReadInContext={handleReadInContext}
                      onSelectPassage={isDesktop ? (p) => handleSelectPassageForReader(p, message.passages!) : undefined}
                      isDesktop={isDesktop}
                    />
                  </div>
                </div>
              ) : (
                <MessageBubble key={message.id} $isUser={message.isUser}>
                  {message.isUser ? message.text : <MarkdownMessage content={message.text} />}
                </MessageBubble>
              )
            ))}

            {isStreaming && streamingResponse && (
              <StreamingBubble $isUser={false}>
                <MarkdownMessage content={streamingResponse} />
                <StreamingCursor />
              </StreamingBubble>
            )}

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

          <FloatingInputArea>
            <InputLabel>
              {activeMode === 'refine_prose'
                ? 'Share a moment or feeling'
                : 'Ask a question or search across all volumes'}
            </InputLabel>
            <InputPill>
              <Input
                type="text"
                placeholder={activeMode === 'refine_prose'
                  ? "Describe a moment \u2014 I'll help you see it through Proust's eyes"
                  : 'What are you curious about in Proust?'}
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
            </InputPill>
          </FloatingInputArea>
        </ConversationPane>

        {readerOpen && (
          <>
            <Divider onMouseDown={handleDividerMouseDown} />
            <ReaderPanel
              passage={selectedPassage}
              allPassages={selectedPassageGroup}
              onClose={() => setSelectedPassage(null)}
              onBookmark={handleBookmark}
              isBookmarked={isBookmarked}
              onReadInContext={handleReadInContext}
              onSelectPassage={(p) => setSelectedPassage(p)}
            />
          </>
        )}
      </ChatContent>
    </ChatContainer>
  );
};

export default ChatPage;
