import { useState, useCallback, useRef } from 'react';
import i18n from '../i18n';
import { Passage, QueryMetadata } from './useStreamingQuery';

export interface Message {
  id: string;
  text: string;
  isUser: boolean;
  passages?: Passage[];
  metadata?: QueryMetadata;
  /** Set when the user stopped generation mid-stream; rendered as a localized meta note. */
  stopped?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  mode: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  mode: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

const INDEX_KEY = 'proust-sessions-index';
const SESSION_KEY_PREFIX = 'proust-session-';
const MAX_SESSIONS = 50;
const MAX_PASSAGE_TEXT = 500;

function readIndex(): ChatSessionSummary[] {
  try {
    const raw = localStorage.getItem(INDEX_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeIndex(index: ChatSessionSummary[]) {
  localStorage.setItem(INDEX_KEY, JSON.stringify(index));
}

function readSession(id: string): ChatSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY_PREFIX + id);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeSession(session: ChatSession) {
  // Truncate passage text before saving
  const trimmed: ChatSession = {
    ...session,
    messages: session.messages.map(m => ({
      ...m,
      passages: m.passages?.map(p => ({
        ...p,
        text: p.text.length > MAX_PASSAGE_TEXT
          ? p.text.slice(0, MAX_PASSAGE_TEXT) + '...'
          : p.text,
      })),
    })),
  };
  try {
    localStorage.setItem(SESSION_KEY_PREFIX + session.id, JSON.stringify(trimmed));
  } catch (e) {
    console.warn('Failed to write session to localStorage:', e);
  }
}

function deleteSessionStorage(id: string) {
  localStorage.removeItem(SESSION_KEY_PREFIX + id);
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function deriveTitle(messages: Message[]): string {
  const firstUser = messages.find(m => m.isUser);
  if (!firstUser) return i18n.t('chat.newConversation');
  const text = firstUser.text.trim();
  return text.length > 50 ? text.slice(0, 50) + '...' : text;
}

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>(() => readIndex());
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  // Track the last saved message count to avoid redundant writes
  const lastSavedRef = useRef<{ id: string; count: number } | null>(null);

  const refreshIndex = useCallback(() => {
    const index = readIndex();
    setSessions(index);
    return index;
  }, []);

  const createSession = useCallback((mode: string): ChatSession => {
    const now = new Date().toISOString();
    const session: ChatSession = {
      id: generateId(),
      title: i18n.t('chat.newConversation'),
      mode,
      createdAt: now,
      updatedAt: now,
      messages: [],
    };

    // Save session data
    writeSession(session);

    // Update index
    let index = readIndex();
    index.unshift({
      id: session.id,
      title: session.title,
      mode: session.mode,
      createdAt: session.createdAt,
      updatedAt: session.updatedAt,
      messageCount: 0,
    });

    // Evict oldest if over limit
    while (index.length > MAX_SESSIONS) {
      const evicted = index.pop()!;
      deleteSessionStorage(evicted.id);
    }

    writeIndex(index);
    setSessions(index);
    setActiveSessionId(session.id);
    lastSavedRef.current = { id: session.id, count: 0 };

    return session;
  }, []);

  const saveSession = useCallback((id: string, messages: Message[], mode: string) => {
    // Skip if nothing changed
    if (
      lastSavedRef.current &&
      lastSavedRef.current.id === id &&
      lastSavedRef.current.count === messages.length
    ) {
      return;
    }

    const existing = readSession(id);
    if (!existing) return;

    const title = deriveTitle(messages);
    const now = new Date().toISOString();

    const updated: ChatSession = {
      ...existing,
      title,
      mode,
      updatedAt: now,
      messages,
    };

    writeSession(updated);

    // Update index
    let index = readIndex();
    const idx = index.findIndex(s => s.id === id);
    if (idx !== -1) {
      index[idx] = {
        ...index[idx],
        title,
        mode,
        updatedAt: now,
        messageCount: messages.length,
      };
      // Move to top
      const [item] = index.splice(idx, 1);
      index.unshift(item);
    }

    writeIndex(index);
    setSessions(index);
    lastSavedRef.current = { id, count: messages.length };
  }, []);

  const loadSession = useCallback((id: string): ChatSession | null => {
    const session = readSession(id);
    if (session) {
      setActiveSessionId(id);
      lastSavedRef.current = { id, count: session.messages.length };
    }
    return session;
  }, []);

  const deleteSession = useCallback((id: string) => {
    deleteSessionStorage(id);

    let index = readIndex();
    index = index.filter(s => s.id !== id);
    writeIndex(index);
    setSessions(index);

    if (activeSessionId === id) {
      setActiveSessionId(null);
    }
  }, [activeSessionId]);

  const getMostRecentSession = useCallback((): ChatSession | null => {
    const index = readIndex();
    if (index.length === 0) return null;
    return readSession(index[0].id);
  }, []);

  return {
    sessions,
    activeSessionId,
    createSession,
    saveSession,
    loadSession,
    deleteSession,
    getMostRecentSession,
    refreshIndex,
  };
}

export default useChatSessions;
