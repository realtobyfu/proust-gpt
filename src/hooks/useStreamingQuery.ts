import { useState, useRef, useCallback } from 'react';

export interface Passage {
  book: string;
  chapter: string;
  text: string;
  text_fr?: string;
  volume?: number;
  index?: number;
  relevance_summary?: string;
  citation_index?: number;
}

export interface QueryMetadata {
  synthesis?: string;
  passage_count?: number;
  query_echo?: string;
}

interface StreamEvent {
  type: 'token' | 'sources' | 'metadata' | 'status' | 'done' | 'error';
  token?: string;
  passages?: Passage[];
  synthesis?: string;
  passage_count?: number;
  query_echo?: string;
  status?: string;
  done?: boolean;
  error?: string;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface StreamingQueryResult {
  response: string;
  passages: Passage[];
  passagesRef: React.RefObject<Passage[]>;
  metadata: QueryMetadata | null;
  status: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  query: (question: string, mode: 'explore' | 'reflect', lang?: string, history?: HistoryMessage[]) => Promise<void>;
  abort: () => void;
  reset: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * React hook for streaming queries using Server-Sent Events.
 *
 * Supports two modes:
 * - 'explore': RAG-based passage retrieval with LLM summary
 * - 'reflect': Proustian reflection conversation
 *
 * @param options.fallbackToNonStreaming - If true, falls back to non-streaming if streaming fails
 */
export function useStreamingQuery(options: {
  fallbackToNonStreaming?: boolean;
} = {}): StreamingQueryResult {
  const { fallbackToNonStreaming = true } = options;

  const [response, setResponse] = useState('');
  const [passages, setPassages] = useState<Passage[]>([]);
  const [metadata, setMetadata] = useState<QueryMetadata | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const passagesRef = useRef<Passage[]>([]);
  const parseFailCountRef = useRef(0);

  const reset = useCallback(() => {
    setResponse('');
    setPassages([]);
    passagesRef.current = [];
    setMetadata(null);
    setStatus(null);
    setError(null);
    setIsLoading(false);
    setIsStreaming(false);
  }, []);

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (readerRef.current) {
      readerRef.current.cancel();
      readerRef.current = null;
    }
    setIsLoading(false);
    setIsStreaming(false);
  }, []);

  const queryNonStreaming = useCallback(async (
    question: string,
    mode: 'explore' | 'reflect',
    lang: string = 'en',
    history?: HistoryMessage[]
  ): Promise<void> => {
    const endpoint = mode === 'reflect'
      ? `${API_BASE_URL}/api/reflect`
      : `${API_BASE_URL}/api/explore_lost_time`;

    const body: Record<string, unknown> = { query: question, message: question, lang };
    if (history && history.length > 0) {
      body.history = history;
    }

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (mode === 'reflect') {
      setResponse(data.reply || '');
    } else {
      setResponse(data.reply || '');
      setPassages(data.passages || []);
    }
  }, []);

  const queryStreaming = useCallback(async (
    question: string,
    mode: 'explore' | 'reflect',
    lang: string = 'en',
    history?: HistoryMessage[]
  ): Promise<void> => {
    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    const endpoint = mode === 'reflect'
      ? `${API_BASE_URL}/api/reflect/stream`
      : `${API_BASE_URL}/api/explore_lost_time/stream`;

    const body: Record<string, unknown> = { query: question, message: question, lang };
    if (history && history.length > 0) {
      body.history = history;
    }

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: abortControllerRef.current.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('No response body');
    }

    setIsStreaming(true);
    const reader = response.body.getReader();
    readerRef.current = reader;
    const decoder = new TextDecoder();
    let buffer = '';

    const processSSEBlock = (block: string) => {
      // Reassemble multi-line data: fields (SSE spec: client concatenates them)
      const dataLines = block.split('\n')
        .filter(l => l.startsWith('data: '))
        .map(l => l.slice(6));
      if (dataLines.length === 0) return;
      const jsonStr = dataLines.join('');  // concatenate chunks

      // Pre-parse diagnostic (fires even if JSON.parse fails)
      if (jsonStr.length > 200) {
        console.log(`[SSE] raw ${jsonStr.length}B (${dataLines.length} lines): ${jsonStr.slice(0, 60)}...`);
      }

      try {
        const event: StreamEvent = JSON.parse(jsonStr);

        console.log(`[SSE] type=${event.type} size=${jsonStr.length}B` +
          (event.type === 'sources'
            ? ` passages=${event.passages?.length ?? 0}`
            : ''));

        switch (event.type) {
          case 'token':
            if (event.token) {
              setStatus(null);
              setResponse(prev => prev + event.token);
            }
            break;

          case 'status':
            if (event.status) {
              setStatus(event.status);
            }
            break;

          case 'sources':
            if (event.passages) {
              setPassages(prev => {
                const updated = [...prev, ...event.passages!];
                passagesRef.current = updated;
                return updated;
              });
            }
            break;

          case 'metadata':
            setMetadata({
              synthesis: event.synthesis,
              passage_count: event.passage_count,
              query_echo: event.query_echo,
            });
            break;

          case 'error':
            throw new Error(event.error || 'Unknown streaming error');

          case 'done':
            // Stream complete
            break;
        }
      } catch (parseError) {
        // Re-throw actual errors (from 'error' events)
        if (parseError instanceof Error && parseError.message !== 'Unknown streaming error'
            && !String(parseError).includes('JSON')) {
          throw parseError;
        }
        parseFailCountRef.current += 1;
        console.warn(`[SSE] PARSE FAIL (${dataLines.length} lines, ${jsonStr.length}B):`,
          jsonStr.slice(0, 200), parseError);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages (each block is separated by \n\n)
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || ''; // Keep incomplete message in buffer

        for (const block of blocks) {
          processSSEBlock(block);
        }
      }

      // Flush the decoder and process any remaining buffered events.
      // On some proxies (e.g. Render), the final SSE events (sources, done)
      // may arrive in the last chunk without a trailing \n\n, leaving them
      // stranded in the buffer when the stream closes.
      buffer += decoder.decode(); // flush any remaining bytes
      if (buffer.trim()) {
        const remaining = buffer.split('\n\n');
        for (const block of remaining) {
          processSSEBlock(block);
        }
      }

      console.log(`[SSE] Stream complete. passages=${passagesRef.current.length}, parseFailures=${parseFailCountRef.current}`);
    } finally {
      readerRef.current = null;
    }
  }, []);

  const query = useCallback(async (
    question: string,
    mode: 'explore' | 'reflect',
    lang: string = 'en',
    history?: HistoryMessage[]
  ): Promise<void> => {
    // Reset state
    setResponse('');
    setPassages([]);
    passagesRef.current = [];
    parseFailCountRef.current = 0;
    setMetadata(null);
    setStatus(null);
    setError(null);
    setIsLoading(true);
    setIsStreaming(false);

    try {
      // Try streaming first
      await queryStreaming(question, mode, lang, history);
    } catch (streamError) {
      // Check if aborted
      if (streamError instanceof Error && streamError.name === 'AbortError') {
        return; // User aborted, don't show error
      }

      console.warn('Streaming failed, error:', streamError);

      // Fallback to non-streaming if enabled
      if (fallbackToNonStreaming) {
        try {
          setResponse('');
          setPassages([]);
          await queryNonStreaming(question, mode, lang, history);
        } catch (fallbackError) {
          setError(fallbackError instanceof Error ? fallbackError.message : 'Unknown error');
        }
      } else {
        setError(streamError instanceof Error ? streamError.message : 'Unknown error');
      }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      abortControllerRef.current = null;

      // Surface a warning if SSE parse failures occurred and no passages arrived
      if (parseFailCountRef.current > 0 && passagesRef.current.length === 0 && mode === 'explore') {
        console.warn(`${parseFailCountRef.current} SSE event(s) failed to parse and no passages were received`);
        setError('Passage data was lost in transit. Please try again.');
      }
    }
  }, [queryStreaming, queryNonStreaming, fallbackToNonStreaming]);

  return {
    response,
    passages,
    passagesRef,
    metadata,
    status,
    isLoading,
    isStreaming,
    error,
    query,
    abort,
    reset,
  };
}

export default useStreamingQuery;
