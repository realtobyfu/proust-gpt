import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import styled, { keyframes } from 'styled-components';
import PassageCard from './components/PassageCard';
import ReaderPanel from './components/ReaderPanel';
import MarkdownMessage from './components/MarkdownMessage';
import LanguageSwitcher from './components/LanguageSwitcher';
import { useLanguage } from './contexts/LanguageContext';
import { useStreamingQuery, Passage, HistoryMessage } from './hooks/useStreamingQuery';
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

const pulse = keyframes`
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
`;

const LoadingIndicator = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  color: #8b4513;
  text-align: center;
  margin: 1rem 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
`;

const LoadingDot = styled.span<{ $delay: string }>`
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #8b4513;
  animation: ${pulse} 1.4s ease-in-out infinite;
  animation-delay: ${props => props.$delay};
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

const NewChatRow = styled.div`
  display: flex;
  gap: 6px;
  margin-bottom: 0.5rem;
`;

const NewChatButton = styled.button<{ $mode?: 'explore' | 'reflect' }>`
  flex: 1;
  padding: 0.4rem 0;
  background: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.06)' : 'rgba(139, 69, 19, 0.08)'};
  border: 1px dashed ${props => props.$mode === 'reflect' ? '#8a9b8a' : '#c4a882'};
  border-radius: 8px;
  color: ${props => props.$mode === 'reflect' ? '#5a6b5a' : '#8b4513'};
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  line-height: 1.2;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  transition: background 0.2s ease;

  &:hover {
    background: ${props => props.$mode === 'reflect' ? 'rgba(90, 107, 90, 0.15)' : 'rgba(139, 69, 19, 0.15)'};
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
  'Why does the narrator say we are "healed of suffering only by experiencing it to the full"?',
  'How does Proust describe the gap between who we imagine someone to be and who they really are?',
  'What does the steeple of Martinville reveal about artistic vocation?',
  'How does the novel portray the difference between habit and genuine feeling?',
  'What does Proust mean when he says that desire changes the thing desired?',
  'How does social climbing destroy authenticity in the novel?',
  'What is the relationship between places and the self in Proust?',
  'How does the death of Bergotte reflect on the meaning of art?',
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
  'I realized I was remembering something wrong',
  'The person I was jealous of turned out to be unhappy too',
  'I found an old photograph and did not recognize my own expression',
  'The difference between the friendship I imagined and the one I had',
  'Something ended so gradually I never noticed it happening',
  'I caught myself performing for someone whose opinion no longer matters',
  'A conversation I keep replaying, changing what I said',
  'The quiet grief of outgrowing a version of yourself',
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

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Extract cited [N] indices from response text (single-digit only). */
function extractCitedIndices(text: string): Set<number> {
  const indices = new Set<number>();
  const re = /\[(\d)\]/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    indices.add(parseInt(m[1], 10));
  }
  return indices;
}

// ── Component ────────────────────────────────────────────────────────────────

const ChatPage: React.FC = () => {
  const { t } = useTranslation();
  const { language } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const { mode: locationMode, prompt, resumeLastSession } = location.state || { mode: 'explore_lost_time', prompt: '', resumeLastSession: false };
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isDesktop = useIsDesktop();

  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState<string>(locationMode || 'explore_lost_time');
  const [bookmarks, setBookmarks] = useLocalStorage<Bookmark[]>('proust-bookmarks', []);
  const [, setLastPosition] = useLocalStorage<LastPassagePosition | null>('proust-last-position', null);

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
  const hasInitializedRef = useRef(false);
  // Keep refs in sync for save-on-unmount (closures in cleanup capture stale state)
  const messagesRef = useRef<Message[]>([]);
  const activeModeRef = useRef(activeMode);
  messagesRef.current = messages;
  activeModeRef.current = activeMode;

  // Use streaming query hook
  const {
    response: streamingResponse,
    passages: streamingPassages,
    passagesRef: streamingPassagesRef,
    metadata: streamingMetadata,
    status: streamingStatus,
    isLoading,
    isStreaming,
    error,
    query: streamQuery,
    abort,
    reset: resetStream,
  } = useStreamingQuery({ fallbackToNonStreaming: true });

  // Session-aware initialization (guarded to prevent duplicate session creation)
  useEffect(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;

    if (resumeLastSession) {
      const recent = getMostRecentSession();
      if (recent && recent.messages.length > 0) {
        currentSessionIdRef.current = recent.id;
        setMessages(recent.messages);
        setActiveMode(recent.mode);
      } else {
        const session = createSession('explore_lost_time');
        currentSessionIdRef.current = session.id;
        setActiveMode('explore_lost_time');
      }
      navigate(location.pathname, { replace: true, state: {} });
      return;
    }

    if (prompt) {
      const mode = locationMode || 'explore_lost_time';
      // Reuse the most recent empty session instead of creating a duplicate
      const recent = getMostRecentSession();
      let session;
      if (recent && recent.messages.length === 0) {
        session = recent;
      } else {
        session = createSession(mode);
      }
      currentSessionIdRef.current = session.id;
      setActiveMode(mode);
      navigate(location.pathname, { replace: true, state: {} });
      handleSendMessage(prompt);
    } else if (!locationMode) {
      // No location state at all (page refresh) — resume most recent session
      const recent = getMostRecentSession();
      if (recent && recent.messages.length > 0) {
        currentSessionIdRef.current = recent.id;
        setMessages(recent.messages);
        setActiveMode(recent.mode);
      } else {
        const session = createSession('explore_lost_time');
        currentSessionIdRef.current = session.id;
        setActiveMode('explore_lost_time');
      }
    } else {
      const mode = locationMode;
      // Reuse the most recent empty session if it matches the requested mode
      const recent = getMostRecentSession();
      if (recent && recent.messages.length === 0 && recent.mode === mode) {
        currentSessionIdRef.current = recent.id;
        setActiveMode(mode);
      } else {
        const session = createSession(mode);
        currentSessionIdRef.current = session.id;
        setActiveMode(mode);
      }
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

  // Save on page close/refresh and on component unmount (navigation away)
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (currentSessionIdRef.current && messagesRef.current.length > 0) {
        saveSession(currentSessionIdRef.current, messagesRef.current, activeModeRef.current);
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Save on unmount (e.g. navigating to another route via React Router)
      if (currentSessionIdRef.current && messagesRef.current.length > 0) {
        saveSession(currentSessionIdRef.current, messagesRef.current, activeModeRef.current);
      }
    };
  }, [saveSession]);

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

  const handleNewConversation = useCallback((mode?: string) => {
    if (currentSessionIdRef.current && messages.length > 0) {
      saveSession(currentSessionIdRef.current, messages, activeMode);
    }
    const newMode = mode || activeMode;
    const session = createSession(newMode);
    currentSessionIdRef.current = session.id;
    setMessages([]);
    setActiveMode(newMode);
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

  // When streaming completes, add the response as a message, save immediately, and track position
  useEffect(() => {
    if (!isLoading && !isStreaming && streamingResponse) {
      // Use ref as fallback — protects against React batching edge cases
      // where streamingPassages state might be stale
      const finalPassages = streamingPassages.length > 0
        ? streamingPassages
        : (streamingPassagesRef.current ?? []);

      const aiMessage: Message = {
        id: Date.now().toString(),
        text: streamingResponse,
        isUser: false,
        passages: finalPassages.length > 0 ? finalPassages : undefined,
        metadata: streamingMetadata || undefined,
      };
      setMessages(prev => {
        const updated = [...prev, aiMessage];
        // Save immediately rather than waiting for the auto-save effect,
        // which runs on the next render and can be missed if the user navigates away
        if (currentSessionIdRef.current) {
          saveSession(currentSessionIdRef.current, updated, activeMode);
        }
        return updated;
      });

      if (finalPassages.length > 0) {
        const lastPassage = finalPassages[finalPassages.length - 1];
        setLastPosition({
          book: lastPassage.book || "Unknown",
          chapter: lastPassage.chapter || "Unknown",
          index: lastPassage.index,
        });
      }

      resetStream();
    }
  }, [isLoading, isStreaming, streamingResponse, streamingPassages, streamingPassagesRef, streamingMetadata, resetStream, activeMode, saveSession]);

  const getModeDisplay = () => {
    switch (activeMode) {
      case 'explore_lost_time':
        return t('chat.exploringMode');
      case 'refine_prose':
        return t('chat.reflectingMode');
      default:
        return t('chat.readingMode');
    }
  };

  const handleSendMessage = async (message: string = userInput) => {
    if (!message.trim() || isLoading) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      text: message,
      isUser: true
    };

    // Build conversation history from recent messages (last 6)
    const recentMessages = [...messages].slice(-6);
    const history: HistoryMessage[] = recentMessages.map(m => ({
      role: m.isUser ? 'user' as const : 'assistant' as const,
      content: m.text,
    }));

    setMessages(prev => [...prev, newMessage]);
    setUserInput('');
    setSelectedPassage(null);

    const queryMode = activeMode === 'refine_prose' ? 'reflect' : 'explore';
    await streamQuery(message, queryMode, language, history.length > 0 ? history : undefined);
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
      const apiBase = import.meta.env.VITE_API_BASE_URL || '';
      const res = await fetch(`${apiBase}/api/read/locate?index=${passage.index}`);
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
          <NewChatRow>
            <NewChatButton $mode="explore" onClick={() => handleNewConversation('explore_lost_time')} title={t('chat.modeExplore')}>
              + {t('chat.modeExplore')}
            </NewChatButton>
            <NewChatButton $mode="reflect" onClick={() => handleNewConversation('refine_prose')} title={t('chat.modeReflect')}>
              + {t('chat.modeReflect')}
            </NewChatButton>
          </NewChatRow>
          <SidebarTitle>{t('chat.conversations')}</SidebarTitle>
          {sessions.length === 0 ? (
            <SidebarItem style={{ color: '#aaa', cursor: 'default' }}>
              {t('chat.noConversations')}
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
                    {s.mode === 'refine_prose' ? t('chat.modeReflect') : t('chat.modeExplore')}
                  </SessionModeTag>
                  {new Date(s.updatedAt).toLocaleDateString()}
                </SessionMeta>
                <DeleteButton
                  className="delete-btn"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  title={t('chat.deleteConversation')}
                >
                  &times;
                </DeleteButton>
              </SessionItem>
            ))
          )}
        </SidebarSection>

        <SidebarSection>
          <SidebarTitle>{t('chat.characters')}</SidebarTitle>
          <SidebarList>
            {characters.map(char => (
              <SidebarItem
                key={char}
                onClick={() => setUserInput(t('chat.tellMeAbout', { character: char }))}
              >
                {char}
              </SidebarItem>
            ))}
          </SidebarList>
        </SidebarSection>

        <SidebarSection>
          <SidebarTitle>{t('chat.bookmarks', { count: bookmarks.length })}</SidebarTitle>
          <SidebarList>
            {bookmarks.length === 0 ? (
              <SidebarItem style={{ color: '#aaa', cursor: 'default' }}>
                {t('chat.noBookmarks')}
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
              <Link to="/about" style={{ color: '#8b4513', fontFamily: "'IBM Plex Sans', sans-serif", fontSize: '0.9rem', textDecoration: 'underline' }}>
                {t('common.about')}
              </Link>
              <LanguageSwitcher />
            </div>
          </Header>

          <MessagesArea>
            {messages.length === 0 && !isLoading && !isStreaming && (
              <EmptyState>
                <EmptyStateTitle>
                  {activeMode === 'refine_prose'
                    ? t('chat.emptyReflect')
                    : t('chat.emptyExplore')}
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

            {messages.map(message => {
              if (message.isUser) {
                return (
                  <MessageBubble key={message.id} $isUser>
                    {message.text}
                  </MessageBubble>
                );
              }

              // Determine which passages were actually cited
              const allPassages = message.passages || [];
              const citedIndices = extractCitedIndices(message.text);
              const citedPassages = allPassages.filter(
                p => p.citation_index != null && citedIndices.has(p.citation_index)
              );
              // Show cited passages if any, otherwise fall back to all passages
              const displayPassages = citedPassages.length > 0 ? citedPassages : allPassages;
              const hasPassages = displayPassages.length > 0;

              return (
                <div key={message.id}>
                  {message.text && (
                    <MessageBubble $isUser={false}>
                      <MarkdownMessage
                        content={message.text}
                        passages={allPassages}
                        onCitationClick={(n) => {
                          const target = allPassages.find(p => p.citation_index === n);
                          if (target && isDesktop) {
                            handleSelectPassageForReader(target, displayPassages);
                          } else {
                            // Scroll to the passage carousel card
                            const el = document.getElementById(`passage-carousel-${message.id}`);
                            el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                          }
                        }}
                      />
                    </MessageBubble>
                  )}

                  {message.metadata?.synthesis && (
                    <SynthesisBanner>{message.metadata.synthesis}</SynthesisBanner>
                  )}

                  {hasPassages && (
                    <>
                      <ResultsHeader>
                        {t('chat.passagesFound', { count: displayPassages.length })}
                      </ResultsHeader>

                      <div id={`passage-carousel-${message.id}`} style={{ alignSelf: 'flex-start', maxWidth: '80%' }}>
                        <PassageCard
                          passages={displayPassages}
                          onBookmark={handleBookmark}
                          isBookmarked={isBookmarked}
                          onReadInContext={handleReadInContext}
                          onSelectPassage={isDesktop ? (p) => handleSelectPassageForReader(p, displayPassages) : undefined}
                          isDesktop={isDesktop}
                        />
                      </div>
                    </>
                  )}
                </div>
              );
            })}

            {/* Show streaming bubble while actively streaming OR while waiting for commit */}
            {((isStreaming && streamingResponse) || (!isLoading && !isStreaming && streamingResponse)) && (
              <StreamingBubble $isUser={false}>
                <MarkdownMessage content={streamingResponse} />
                {isStreaming && <StreamingCursor />}
              </StreamingBubble>
            )}

            {error && (
              <ErrorMessage>
                {t('common.error')}: {error}
              </ErrorMessage>
            )}

            {isLoading && !streamingResponse && (
              <LoadingIndicator>
                <LoadingDot $delay="0s" />
                <LoadingDot $delay="0.2s" />
                <LoadingDot $delay="0.4s" />
                {streamingStatus || t('chat.searching')}
              </LoadingIndicator>
            )}

            <div ref={messagesEndRef} />
          </MessagesArea>

          <FloatingInputArea>
            <InputLabel>
              {activeMode === 'refine_prose'
                ? t('chat.inputLabelReflect')
                : t('chat.inputLabelExplore')}
            </InputLabel>
            <InputPill>
              <Input
                type="text"
                placeholder={activeMode === 'refine_prose'
                  ? t('chat.placeholderReflect')
                  : t('chat.placeholderExplore')}
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
              />
              {isStreaming ? (
                <StopButton onClick={handleStopGenerating}>
                  {t('common.stop')}
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
