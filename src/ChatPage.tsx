import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReaderPanel from './components/ReaderPanel';
import LanguageSwitcher from './components/LanguageSwitcher';
import ChatSidebar from './components/chat/ChatSidebar';
import MessageList from './components/chat/MessageList';
import ChatInput from './components/chat/ChatInput';
import { useLanguage } from './contexts/LanguageContext';
import { useStreamingQuery, Passage, HistoryMessage } from './hooks/useStreamingQuery';
import { useLocalStorage } from './hooks/useLocalStorage';
import { useChatSessions, Message } from './hooks/useChatSessions';
import { Bookmark, bookmarkMatches } from './types';
import { copyToClipboard } from './utils/clipboard';

const STREAM_DEBUG = import.meta.env.DEV || import.meta.env.VITE_STREAM_DEBUG === 'true';

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

// ── Styled components (extracted to ChatPage.styles.ts, I1) ──
import {
  ChatContainer,
  ChatContent,
  ConversationPane,
  Divider,
  Header,
  BackButton,
  ModeSwitcher,
  ModeSwitchButton,
  HeaderTextButton,
  CopyNotice,
  HamburgerButton,
} from './ChatPage.styles';

// ── Prompt pools ─────────────────────────────────────────────────────────────
// Suggestion prompts live in the i18n files (chat.explorePromptPool /
// chat.reflectPromptPool) so they follow the selected UI language.

function shuffleArray<T>(arr: T[]): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// ── Interfaces ───────────────────────────────────────────────────────────────

interface LastPassagePosition {
  book: string;
  chapter: string;
  index?: number;
}

// ── Component ────────────────────────────────────────────────────────────────

const ChatPage: React.FC = () => {
  const { t } = useTranslation();
  const { language } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const { mode: locationMode, prompt, resumeLastSession } = location.state || { mode: 'explore_lost_time', prompt: '', resumeLastSession: false };
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamCommittedRef = useRef(false);
  const isDesktop = useIsDesktop();
  const logStreamCommit = useCallback((message: string, details?: Record<string, unknown>) => {
    if (!STREAM_DEBUG) return;
    if (details) {
      console.log(`[StreamCommit] ${message}`, details);
    } else {
      console.log(`[StreamCommit] ${message}`);
    }
  }, []);

  const [messages, setMessages] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeMode, setActiveMode] = useState<string>(locationMode || 'explore_lost_time');
  const [bookmarks, setBookmarks] = useLocalStorage<Bookmark[]>('proust-bookmarks', []);
  const [, setLastPosition] = useLocalStorage<LastPassagePosition | null>('proust-last-position', null);

  // Shuffled suggestion prompts (sourced from i18n so they match the UI language)
  const exploreSuggestions = useMemo(() => {
    const pool = t('chat.explorePromptPool', { returnObjects: true });
    return shuffleArray(Array.isArray(pool) ? pool as string[] : []).slice(0, 3);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);
  const reflectSuggestions = useMemo(() => {
    const pool = t('chat.reflectPromptPool', { returnObjects: true });
    return shuffleArray(Array.isArray(pool) ? pool as string[] : []).slice(0, 3);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

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
    responseRef: streamingResponseRef,
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
    const saveWithPartialResponse = () => {
      let msgs = messagesRef.current;
      // If there's an uncommitted streaming response, append it as a partial message
      if (!streamCommittedRef.current && streamingResponseRef.current) {
        const partialMessage: Message = {
          id: Date.now().toString(),
          text: streamingResponseRef.current,
          isUser: false,
          passages: (streamingPassagesRef.current ?? []).length > 0
            ? (streamingPassagesRef.current ?? [])
            : undefined,
        };
        msgs = [...msgs, partialMessage];
      }
      if (currentSessionIdRef.current && msgs.length > 0) {
        saveSession(currentSessionIdRef.current, msgs, activeModeRef.current);
      }
    };

    const handleBeforeUnload = () => {
      saveWithPartialResponse();
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Save on unmount (e.g. navigating to another route via React Router)
      saveWithPartialResponse();
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

  // Keyboard resize for the split divider (arrow keys)
  const handleDividerKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setSplitPercent(prev => Math.max(30, prev - 2));
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setSplitPercent(prev => Math.min(75, prev + 2));
    }
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
    if (!window.confirm(t('chat.deleteConfirm'))) return;
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
  }, [deleteSession, getMostRecentSession, loadSession, createSession, activeMode, resetStream, t]);

  // When streaming completes, add the response as a message, save immediately, and track position.
  // We set streamCommittedRef instead of calling resetStream() to avoid a flash where the
  // streaming bubble disappears (text gone) before the committed message renders (text back).
  // The ref hides the streaming bubble in the SAME render that adds the committed message.
  useEffect(() => {
    if (!isLoading && !isStreaming && streamingResponse && !streamCommittedRef.current) {
      streamCommittedRef.current = true;

      // Use ref as fallback — protects against React batching edge cases
      // where streamingPassages state might be stale
      const finalPassages = streamingPassages.length > 0
        ? streamingPassages
        : (streamingPassagesRef.current ?? []);
      logStreamCommit('commit effect entered', {
        responseLength: streamingResponse.length,
        passages: finalPassages.length,
        isLoading,
        isStreaming,
      });

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
        logStreamCommit('message saved', {
          messageId: aiMessage.id,
          passages: finalPassages.length,
          totalMessages: updated.length,
        });
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

      // Don't call resetStream() here — clearing streamingResponse causes a
      // visible flash where text disappears before the committed message renders.
      // Streaming state is cleaned up when the next query starts.
    }
  }, [isLoading, isStreaming, streamingResponse, streamingPassages, streamingPassagesRef, streamingMetadata, activeMode, saveSession, logStreamCommit]);

  const getModeDisplay = () => {
    switch (activeMode) {
      case 'explore_lost_time':
        return t('chat.exploringMode');
      case 'reflect':
        return t('chat.reflectingMode');
      default:
        return t('chat.readingMode');
    }
  };

  const handleSendMessage = async (message: string = userInput) => {
    if (!message.trim() || isLoading) return;
    streamCommittedRef.current = false;

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

    const queryMode = activeMode === 'reflect' ? 'reflect' : 'explore';
    await streamQuery(message, queryMode, language, history.length > 0 ? history : undefined);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoading) {
      handleSendMessage();
    }
  };

  const handleRetry = () => {
    if (isLoading) return;
    const lastUserIdx = messages.map(m => m.isUser).lastIndexOf(true);
    if (lastUserIdx === -1) return;
    const lastUser = messages[lastUserIdx];
    streamCommittedRef.current = false;
    resetStream();
    const priorMessages = messages.slice(0, lastUserIdx).slice(-6);
    const history: HistoryMessage[] = priorMessages.map(m => ({
      role: m.isUser ? 'user' as const : 'assistant' as const,
      content: m.text,
    }));
    const queryMode = activeMode === 'reflect' ? 'reflect' : 'explore';
    streamQuery(lastUser.text, queryMode, language, history.length > 0 ? history : undefined);
  };

  const handleStopGenerating = () => {
    abort();
    if (streamingResponse) {
      const partialMessage: Message = {
        id: Date.now().toString(),
        text: streamingResponse,
        isUser: false,
        stopped: true,
      };
      setMessages(prev => [...prev, partialMessage]);
      resetStream();
    }
  };

  // Mode switching from the header (H3)
  const handleSwitchMode = (mode: string) => {
    if (mode === activeMode) return;
    if (messages.length > 0 && !window.confirm(t('chat.switchModeConfirm'))) return;
    handleNewConversation(mode);
  };

  // Export / share (H5) — markdown to clipboard
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const copyNoticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flashNotice = useCallback((msg: string) => {
    setCopyNotice(msg);
    if (copyNoticeTimer.current) clearTimeout(copyNoticeTimer.current);
    copyNoticeTimer.current = setTimeout(() => setCopyNotice(null), 2200);
  }, []);
  useEffect(() => () => {
    if (copyNoticeTimer.current) clearTimeout(copyNoticeTimer.current);
  }, []);

  const passageToMarkdown = (p: Passage) =>
    `> ${p.text}\n> — ${p.book || 'In Search of Lost Time'}${p.chapter ? `, ${p.chapter}` : ''}`;

  const handleExportConversation = async () => {
    if (messages.length === 0) {
      flashNotice(t('chat.nothingToExport'));
      return;
    }
    const body = messages.map(m => {
      if (m.isUser) return `**You:** ${m.text}`;
      let block = `**ProustGPT:** ${m.text}`;
      if (m.passages && m.passages.length > 0) {
        block += '\n\n' + m.passages.map(passageToMarkdown).join('\n>\n');
      }
      return block;
    }).join('\n\n');
    const md = `# ProustGPT — ${getModeDisplay()}\n\n${body}\n`;
    const ok = await copyToClipboard(md);
    flashNotice(ok ? t('chat.copied') : t('chat.exportFailed'));
  };

  const handleExportBookmarks = async () => {
    if (bookmarks.length === 0) {
      flashNotice(t('chat.nothingToExport'));
      return;
    }
    const body = bookmarks
      .map(b => `> ${b.text}\n> — ${b.book}${b.chapter ? `, ${b.chapter}` : ''}`)
      .join('\n\n');
    const md = `# ProustGPT — ${t('chat.bookmarks', { count: bookmarks.length })}\n\n${body}\n`;
    const ok = await copyToClipboard(md);
    flashNotice(ok ? t('chat.copied') : t('chat.exportFailed'));
  };

  const handleBookmark = (passage: Passage) => {
    setBookmarks(prev => {
      if (prev.some(b => bookmarkMatches(b, passage))) {
        return prev.filter(b => !bookmarkMatches(b, passage));
      }
      return [...prev, {
        id: Date.now().toString(),
        text: passage.text,
        book: passage.book || "Unknown",
        chapter: passage.chapter || "Unknown",
        index: passage.index,
        savedAt: new Date().toISOString(),
      }];
    });
  };

  const isBookmarked = (passage: Passage) => {
    return bookmarks.some(b => bookmarkMatches(b, passage));
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

  return (
    <ChatContainer>
      <ChatSidebar
        sidebarOpen={sidebarOpen}
        sessions={sessions}
        currentSessionId={currentSessionIdRef.current}
        bookmarks={bookmarks}
        language={language}
        onNewConversation={handleNewConversation}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onFillInput={setUserInput}
        onExportBookmarks={handleExportBookmarks}
      />

      <ChatContent ref={chatContentRef}>
        <ConversationPane $readerOpen={readerOpen} $splitPercent={splitPercent}>
          <Header>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <HamburgerButton onClick={() => setSidebarOpen(!sidebarOpen)} aria-label={t('chat.toggleSidebar')} aria-expanded={sidebarOpen}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="3" y1="6" x2="21" y2="6"/>
                  <line x1="3" y1="12" x2="21" y2="12"/>
                  <line x1="3" y1="18" x2="21" y2="18"/>
                </svg>
              </HamburgerButton>
              <BackButton onClick={() => navigate('/')} aria-label={t('common.back')}>&larr;</BackButton>
              <ModeSwitcher role="group" aria-label={getModeDisplay()}>
                <ModeSwitchButton
                  type="button"
                  $mode="explore"
                  $active={activeMode === 'explore_lost_time'}
                  aria-pressed={activeMode === 'explore_lost_time'}
                  onClick={() => handleSwitchMode('explore_lost_time')}
                >
                  {t('chat.modeExplore')}
                </ModeSwitchButton>
                <ModeSwitchButton
                  type="button"
                  $mode="reflect"
                  $active={activeMode === 'reflect'}
                  aria-pressed={activeMode === 'reflect'}
                  onClick={() => handleSwitchMode('reflect')}
                >
                  {t('chat.modeReflect')}
                </ModeSwitchButton>
              </ModeSwitcher>
            </div>
            <div style={{ display: 'flex', gap: '0.9rem', alignItems: 'center' }}>
              {messages.length > 0 && (
                <HeaderTextButton onClick={handleExportConversation} title={t('chat.exportConversation')}>
                  {t('chat.exportConversation')}
                </HeaderTextButton>
              )}
              <Link to="/about" style={{ color: '#8b4513', fontFamily: "'IBM Plex Sans', sans-serif", fontSize: '0.9rem', textDecoration: 'underline' }}>
                {t('common.about')}
              </Link>
              <LanguageSwitcher />
            </div>
          </Header>

          <MessageList
            messages={messages}
            isDesktop={isDesktop}
            isLoading={isLoading}
            isStreaming={isStreaming}
            streamingResponse={streamingResponse}
            streamingStatus={streamingStatus}
            streamCommitted={streamCommittedRef.current}
            error={error}
            activeMode={activeMode}
            exploreSuggestions={exploreSuggestions}
            reflectSuggestions={reflectSuggestions}
            messagesEndRef={messagesEndRef}
            onSendMessage={handleSendMessage}
            onSelectPassageForReader={handleSelectPassageForReader}
            onBookmark={handleBookmark}
            isBookmarked={isBookmarked}
            onReadInContext={handleReadInContext}
            onRetry={handleRetry}
          />

          <ChatInput
            activeMode={activeMode}
            userInput={userInput}
            onUserInput={setUserInput}
            isLoading={isLoading}
            isStreaming={isStreaming}
            onSubmit={handleFormSubmit}
            onStop={handleStopGenerating}
          />
        </ConversationPane>

        {readerOpen && (
          <>
            <Divider
              role="separator"
              aria-orientation="vertical"
              aria-label={t('chat.resizeReader')}
              tabIndex={0}
              onMouseDown={handleDividerMouseDown}
              onKeyDown={handleDividerKeyDown}
            />
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
      {copyNotice && <CopyNotice role="status" aria-live="polite">{copyNotice}</CopyNotice>}
    </ChatContainer>
  );
};

export default ChatPage;
