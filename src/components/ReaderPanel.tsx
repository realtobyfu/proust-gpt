import React, { useCallback, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { useTranslation } from 'react-i18next';
import { Passage } from '../hooks/useStreamingQuery';
import { formatPassageText } from '../utils/formatPassageText';
import { usePassageText, isPassageTruncated } from '../hooks/usePassageText';
import PassageNav from './PassageNav';

interface ReaderPanelProps {
  passage: Passage | null;
  allPassages: Passage[];
  onClose: () => void;
  onBookmark: (passage: Passage) => void;
  isBookmarked: (passage: Passage) => boolean;
  onReadInContext?: (passage: Passage) => void;
  onSelectPassage: (passage: Passage) => void;
}

const slideIn = keyframes`
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
`;

const PanelContainer = styled.div`
  flex: 1;
  min-width: 380px;
  border-left: 1px solid #e0d8cf;
  background: #faf8f5;
  display: flex;
  flex-direction: column;
  animation: ${slideIn} 300ms ease forwards;
  overflow: hidden;

  @media (max-width: 1024px) {
    display: none;
  }
`;

const PanelHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e0d8cf;
  background: #faf8f5;
`;

const CloseButton = styled.button`
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: none;
  color: #8b4513;
  font-size: 1.1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.08);
  }
`;

const SourceChip = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  font-variant: small-caps;
  letter-spacing: 0.05em;
  color: #8b4513;
  background: rgba(139, 69, 19, 0.06);
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
`;

const PanelBody = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 2rem 2.25rem;

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

const PassageText = styled.div`
  font-family: 'Georgia', serif;
  font-size: 1.1rem;
  line-height: 1.95;
  color: #333;
  text-align: justify;
  hyphens: auto;
  margin-bottom: 1.5rem;
`;

const RelevanceSummary = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.88rem;
  font-style: italic;
  color: #666;
  margin-bottom: 1.25rem;
  line-height: 1.7;
`;

const ActionRow = styled.div`
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
`;

const BookmarkButton = styled.button<{ $active: boolean }>`
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.9rem;
  border-radius: 20px;
  border: 1px solid ${props => props.$active ? '#8b4513' : '#d4ccc3'};
  background: ${props => props.$active ? 'rgba(139, 69, 19, 0.1)' : 'transparent'};
  color: #8b4513;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.12);
    border-color: #8b4513;
  }
`;

const ReadInContextButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.4rem 0.9rem;
  border-radius: 20px;
  border: 1px solid #d4ccc3;
  background: transparent;
  color: #8b4513;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.12);
    border-color: #8b4513;
  }

  &::after {
    content: ' →';
  }
`;

const SeeOriginalLink = styled.button`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0;
  transition: color 0.15s ease;

  &:hover {
    color: #6b3410;
    text-decoration: underline;
  }
`;

const UnavailableNote = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.78rem;
  color: #999;
  font-style: italic;
  margin-bottom: 1rem;
`;

const ReaderPanel: React.FC<ReaderPanelProps> = ({
  passage,
  allPassages,
  onClose,
  onBookmark,
  isBookmarked,
  onReadInContext,
  onSelectPassage,
}) => {
  const { t } = useTranslation();

  const {
    showOriginal,
    toggleOriginal,
    displayText,
    showFrUnavailable,
    fetchingFr,
    canShowOriginalToggle,
    sourceLabel,
    loadFullText,
  } = usePassageText(passage, { includeCitation: false });

  // Auto-fetch full text when panel opens with a truncated passage
  useEffect(() => {
    if (passage && passage.index != null && isPassageTruncated(passage)) {
      loadFullText(passage.index);
    }
  }, [passage, loadFullText]);

    const currentIndex = passage ? allPassages.findIndex(p => p.text === passage.text) : -1;
  const hasMultiple = allPassages.length > 1;

  const handleToggleOriginal = useCallback(() => {
    toggleOriginal();
  }, [toggleOriginal]);

  const goTo = useCallback((index: number) => {
    if (index >= 0 && index < allPassages.length) {
      onSelectPassage(allPassages[index]);
    }
  }, [allPassages, onSelectPassage]);

  if (!passage) return null;

  return (
    <PanelContainer>
      <PanelHeader>
        <SourceChip>{sourceLabel}</SourceChip>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {canShowOriginalToggle && (
            <SeeOriginalLink onClick={handleToggleOriginal}>
              {showOriginal ? t('passage.seeTranslation') : t('passage.seeOriginal')}
            </SeeOriginalLink>
          )}
          <CloseButton onClick={onClose} aria-label="Close reader panel">
            &times;
          </CloseButton>
        </div>
      </PanelHeader>

      <PanelBody>
        <PassageText>
          {fetchingFr && showOriginal ? t('common.loading') : formatPassageText(displayText)}
        </PassageText>

        {showFrUnavailable && (
          <UnavailableNote>{t('passage.frenchUnavailable')}</UnavailableNote>
        )}

        {passage.relevance_summary && (
          <RelevanceSummary>{passage.relevance_summary}</RelevanceSummary>
        )}

        <ActionRow>
          <BookmarkButton
            $active={isBookmarked(passage)}
            onClick={() => onBookmark(passage)}
          >
            {isBookmarked(passage) ? t('common.saved') : t('passage.savePassage')}
          </BookmarkButton>
          {onReadInContext && passage.index != null && (
            <ReadInContextButton onClick={() => onReadInContext(passage)}>
              {t('passage.readInContext')}
            </ReadInContextButton>
          )}
        </ActionRow>

        {hasMultiple && (
          <div style={{ borderTop: '1px solid #eee', paddingTop: '1rem' }}>
            <PassageNav
              count={allPassages.length}
              currentIndex={currentIndex}
              onNavigate={(i) => goTo(i)}
            />
          </div>
        )}
      </PanelBody>
    </PanelContainer>
  );
};

export default ReaderPanel;
