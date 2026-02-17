import React, { useState, useCallback, useEffect } from 'react';
import styled, { keyframes } from 'styled-components';
import { useTranslation } from 'react-i18next';
import { Passage } from '../hooks/useStreamingQuery';
import { formatPassageText } from '../utils/formatPassageText';
import { frenchName } from '../utils/frenchNames';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

interface ReaderPanelProps {
  passage: Passage | null;
  allPassages: Passage[];
  onClose: () => void;
  onBookmark: (passage: Passage) => void;
  isBookmarked: (text: string) => boolean;
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

const NavFooter = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem 0;
  border-top: 1px solid #eee;
`;

const NavArrow = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.08);
  }

  &:disabled {
    color: #d4ccc3;
    cursor: default;
    &:hover { background: none; }
  }
`;

const Dot = styled.button<{ $active: boolean }>`
  width: 7px;
  height: 7px;
  border-radius: 50%;
  border: none;
  padding: 0;
  background: ${props => props.$active ? '#8b4513' : '#d4ccc3'};
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;

  &:hover { background: #8b4513; }
  ${props => props.$active && `transform: scale(1.3);`}
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
  const { t, i18n } = useTranslation();
  const [showOriginal, setShowOriginal] = useState(false);
  const [frenchTexts, setFrenchTexts] = useState<Record<number, string | null>>({});
  const [fetchingFr, setFetchingFr] = useState(false);
  const [fullTexts, setFullTexts] = useState<Record<number, { text: string; text_fr?: string }>>({});

  const isTruncated = (p: Passage) =>
    p._truncated === true || p.text?.endsWith('\u2026');

  // Fetch full EN+FR text for truncated passages
  const fetchFullText = useCallback(async (passageIndex: number) => {
    if (fullTexts[passageIndex] !== undefined) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/read/passage_text?index=${passageIndex}&lang=both`);
      const data = await res.json();
      if (data.text) {
        setFullTexts(prev => ({
          ...prev,
          [passageIndex]: { text: data.text, text_fr: data.text_fr || undefined },
        }));
      }
    } catch {
      // Silently fail — user sees the preview text
    }
  }, [fullTexts]);

  // Auto-fetch full text when panel opens with a truncated passage
  useEffect(() => {
    if (passage && passage.index != null && isTruncated(passage) && !fullTexts[passage.index]) {
      fetchFullText(passage.index);
    }
  }, [passage]);

  const currentIndex = passage ? allPassages.findIndex(p => p.text === passage.text) : -1;
  const hasMultiple = allPassages.length > 1;

  const fetchFrenchText = useCallback(async (passageIndex: number) => {
    if (frenchTexts[passageIndex] !== undefined) return;
    setFetchingFr(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/read/passage_text?index=${passageIndex}&lang=fr`);
      const data = await res.json();
      setFrenchTexts(prev => ({
        ...prev,
        [passageIndex]: data.text_unavailable ? null : (data.text || null),
      }));
    } catch {
      setFrenchTexts(prev => ({ ...prev, [passageIndex]: null }));
    } finally {
      setFetchingFr(false);
    }
  }, [frenchTexts]);

  const handleToggleOriginal = useCallback(() => {
    const next = !showOriginal;
    setShowOriginal(next);
    if (next && !passage?.text_fr && passage?.index != null) {
      fetchFrenchText(passage.index);
    }
  }, [showOriginal, passage, fetchFrenchText]);

  const goTo = useCallback((index: number) => {
    if (index >= 0 && index < allPassages.length) {
      onSelectPassage(allPassages[index]);
    }
  }, [allPassages, onSelectPassage]);

  if (!passage) return null;

  const isFr = i18n.language === 'fr';
  const full = passage.index != null ? fullTexts[passage.index] : undefined;
  const enText = full?.text ?? passage.text;
  const frText = full?.text_fr ?? passage.text_fr ?? (passage.index != null ? frenchTexts[passage.index] : undefined);
  let displayText: string;
  if (isFr) {
    displayText = frText || enText;
  } else if (showOriginal && frText) {
    displayText = frText;
  } else {
    displayText = enText;
  }
  const showFrUnavailable = showOriginal && !isFr && !frText && passage.index != null && frenchTexts[passage.index] === null;

  const indexSuffix = passage.index != null ? `, §${passage.index}` : '';
  const sourceLabel = [
    isFr ? frenchName(passage.book || '') || 'À la recherche du temps perdu' : passage.book || 'In Search of Lost Time',
    isFr && passage.chapter ? frenchName(passage.chapter) : passage.chapter,
  ].filter(Boolean).join(' — ') + indexSuffix;

  return (
    <PanelContainer>
      <PanelHeader>
        <SourceChip>{sourceLabel}</SourceChip>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {!isFr && (passage.text_fr || passage.index != null) && (
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
            $active={isBookmarked(passage.text)}
            onClick={() => onBookmark(passage)}
          >
            {isBookmarked(passage.text) ? t('common.saved') : t('passage.savePassage')}
          </BookmarkButton>
          {onReadInContext && passage.index != null && (
            <ReadInContextButton onClick={() => onReadInContext(passage)}>
              {t('passage.readInContext')}
            </ReadInContextButton>
          )}
        </ActionRow>

        {hasMultiple && (
          <NavFooter>
            <NavArrow
              onClick={() => goTo(currentIndex - 1)}
              disabled={currentIndex <= 0}
              aria-label="Previous passage"
            >
              &#8249;
            </NavArrow>
            {allPassages.map((_, i) => (
              <Dot
                key={i}
                $active={i === currentIndex}
                onClick={() => goTo(i)}
                aria-label={`Go to passage ${i + 1}`}
              />
            ))}
            <NavArrow
              onClick={() => goTo(currentIndex + 1)}
              disabled={currentIndex >= allPassages.length - 1}
              aria-label="Next passage"
            >
              &#8250;
            </NavArrow>
          </NavFooter>
        )}
      </PanelBody>
    </PanelContainer>
  );
};

export default ReaderPanel;
