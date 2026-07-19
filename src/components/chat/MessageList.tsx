import React from 'react';
import { useTranslation } from 'react-i18next';
import PassageCard from '../PassageCard';
import MarkdownMessage from '../MarkdownMessage';
import { Message } from '../../hooks/useChatSessions';
import { Passage } from '../../hooks/useStreamingQuery';
import {
  MessagesArea,
  MessageBubble,
  StreamingCursor,
  SynthesisBanner,
  ResultsHeader,
  EmptyState,
  EmptyStateTitle,
  SuggestionChips,
  SuggestionChip,
  StoppedNote,
  ErrorMessage,
  RetryButton,
  LoadingIndicator,
  LoadingDot,
} from '../../ChatPage.styles';

/** Extract cited [N] indices from response text. */
function extractCitedIndices(text: string): Set<number> {
  const indices = new Set<number>();
  const re = /\[(\d+)\]/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    indices.add(parseInt(m[1], 10));
  }
  return indices;
}

interface MessageListProps {
  messages: Message[];
  isDesktop: boolean;
  isLoading: boolean;
  isStreaming: boolean;
  streamingResponse: string;
  streamingStatus: string | null;
  streamCommitted: boolean;
  error: string | null;
  activeMode: string;
  exploreSuggestions: string[];
  reflectSuggestions: string[];
  messagesEndRef: React.RefObject<HTMLDivElement>;
  onSendMessage: (text: string) => void;
  onSelectPassageForReader: (passage: Passage, allPassages: Passage[]) => void;
  onBookmark: (passage: Passage) => void;
  isBookmarked: (passage: Passage) => boolean;
  onReadInContext: (passage: Passage) => void;
  onRetry: () => void;
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  isDesktop,
  isLoading,
  isStreaming,
  streamingResponse,
  streamingStatus,
  streamCommitted,
  error,
  activeMode,
  exploreSuggestions,
  reflectSuggestions,
  messagesEndRef,
  onSendMessage,
  onSelectPassageForReader,
  onBookmark,
  isBookmarked,
  onReadInContext,
  onRetry,
}) => {
  const { t } = useTranslation();

  return (
    <MessagesArea as="main">
      {messages.length === 0 && !isLoading && !isStreaming && (
        <EmptyState>
          <EmptyStateTitle>
            {activeMode === 'reflect' ? t('chat.emptyReflect') : t('chat.emptyExplore')}
          </EmptyStateTitle>
          <SuggestionChips>
            {(activeMode === 'reflect' ? reflectSuggestions : exploreSuggestions).map((text, i) => (
              <SuggestionChip key={i} onClick={() => onSendMessage(text)}>
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
                      onSelectPassageForReader(target, displayPassages);
                    } else {
                      // Scroll to the passage carousel card
                      const el = document.getElementById(`passage-carousel-${message.id}`);
                      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                  }}
                />
              </MessageBubble>
            )}

            {message.stopped && (
              <StoppedNote>{t('chat.stopped')}</StoppedNote>
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
                    onBookmark={onBookmark}
                    isBookmarked={isBookmarked}
                    onReadInContext={onReadInContext}
                    onSelectPassage={isDesktop ? (p) => onSelectPassageForReader(p, displayPassages) : undefined}
                    isDesktop={isDesktop}
                  />
                </div>
              </>
            )}
          </div>
        );
      })}

      {/* Show streaming bubble while actively streaming OR while waiting for commit */}
      {!streamCommitted && ((isStreaming && streamingResponse) || (!isLoading && !isStreaming && streamingResponse)) && (
        <MessageBubble $isUser={false}>
          <MarkdownMessage content={streamingResponse} />
          {isStreaming && <StreamingCursor />}
        </MessageBubble>
      )}

      {error && (
        <ErrorMessage>
          {t('common.error')}: {error}
          {messages.some(m => m.isUser) && (
            <div>
              <RetryButton onClick={onRetry} disabled={isLoading}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M23 4v6h-6M1 20v-6h6" />
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                </svg>
                {t('chat.retry')}
              </RetryButton>
            </div>
          )}
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
  );
};

export default MessageList;
