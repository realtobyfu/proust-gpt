import { useState, useRef, useCallback } from 'react';

export interface Passage {
  book: string;
  chapter: string;
  text: string;
  volume?: number;
  index?: number;
  relevance_summary?: string;
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

export interface StreamingQueryResult {
  response: string;
  passages: Passage[];
  metadata: QueryMetadata | null;
  status: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  query: (question: string, mode: 'explore' | 'reflect', lang?: string) => Promise<void>;
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

  const reset = useCallback(() => {
    setResponse('');
    setPassages([]);
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
    lang: string = 'en'
  ): Promise<void> => {
    const endpoint = mode === 'reflect'
      ? `${API_BASE_URL}/api/reflect`
      : `${API_BASE_URL}/api/explore_lost_time`;

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question, message: question, lang }),
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
    lang: string = 'en'
  ): Promise<void> => {
    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    const endpoint = mode === 'reflect'
      ? `${API_BASE_URL}/api/reflect/stream`
      : `${API_BASE_URL}/api/explore_lost_time/stream`;

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question, message: question, lang }),
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

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // Keep incomplete message in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          try {
            const jsonStr = line.slice(6); // Remove 'data: ' prefix
            const event: StreamEvent = JSON.parse(jsonStr);

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
                  setPassages(event.passages);
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
            console.warn('Failed to parse SSE event:', line, parseError);
          }
        }
      }
    } finally {
      readerRef.current = null;
    }
  }, []);

  const query = useCallback(async (
    question: string,
    mode: 'explore' | 'reflect',
    lang: string = 'en'
  ): Promise<void> => {
    // Reset state
    setResponse('');
    setPassages([]);
    setMetadata(null);
    setStatus(null);
    setError(null);
    setIsLoading(true);
    setIsStreaming(false);

    try {
      // Try streaming first
      await queryStreaming(question, mode, lang);
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
          await queryNonStreaming(question, mode, lang);
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
    }
  }, [queryStreaming, queryNonStreaming, fallbackToNonStreaming]);

  return {
    response,
    passages,
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
