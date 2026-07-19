import React, { useState, useRef, useCallback, useEffect } from 'react';
import styled, { css, keyframes } from 'styled-components';
import { useTranslation } from 'react-i18next';
import { Passage } from '../hooks/useStreamingQuery';
import { usePassageText, isPassageTruncated } from '../hooks/usePassageText';
import PassageNav from './PassageNav';

interface PassageCardProps {
  passages: Passage[];
  onBookmark: (passage: Passage) => void;
  isBookmarked: (passage: Passage) => boolean;
  onReadInContext?: (passage: Passage) => void;
  /** Desktop: clicking opens the reader panel instead of expanding inline */
  onSelectPassage?: (passage: Passage) => void;
  isDesktop?: boolean;
}

const slideLeft = keyframes`
  from { opacity: 0; transform: translateX(40px); }
  to { opacity: 1; transform: translateX(0); }
`;

const slideRight = keyframes`
  from { opacity: 0; transform: translateX(-40px); }
  to { opacity: 1; transform: translateX(0); }
`;

const CardWrapper = styled.div<{ $expanded: boolean }>`
  background: rgba(255, 255, 255, 0.85);
  border-radius: 10px;
  border: 1px solid #e0d8cf;
  margin-bottom: 0.75rem;
  cursor: pointer;
  transition: box-shadow 0.2s ease, transform 0.15s ease;
  position: relative;
  overflow: hidden;

  &:hover {
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.07);
    transform: translateY(-1px);
  }

  ${props => props.$expanded && css`
    cursor: default;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
    transform: none;

    &:hover {
      transform: none;
    }
  `}
`;

const CardInner = styled.div`
  padding: 1.5rem 1.75rem;
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
  margin-bottom: 0.6rem;
`;

const TextPreview = styled.div<{ $expanded: boolean; $maxHeight: string }>`
  font-family: 'Georgia', serif;
  font-size: ${props => props.$expanded ? '1.1rem' : '1.0rem'};
  line-height: 1.9;
  text-align: justify;
  hyphens: auto;
  color: #333;
  position: relative;
  transition: max-height 0.35s ease, font-size 0.2s ease;
  overflow: hidden;
  max-height: ${props => props.$maxHeight};

  ${props => !props.$expanded && css`
    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 2.5em;
      background: linear-gradient(transparent, rgba(255, 255, 255, 0.95));
      pointer-events: none;
    }
  `}
`;

const RelevanceSummary = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.88rem;
  font-style: italic;
  color: #666;
  margin-top: 0.5rem;
  line-height: 1.7;
`;

const BookmarkIcon = styled.button<{ $active: boolean }>`
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  color: ${props => props.$active ? '#8b4513' : '#c4a882'};
  padding: 0.2rem;
  transition: color 0.2s ease, transform 0.15s ease;
  z-index: 2;

  &:hover {
    color: #8b4513;
    transform: scale(1.15);
  }
`;

const CollapseButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0;
  margin-top: 0.75rem;
  transition: color 0.15s ease;

  &:hover {
    color: #6b3410;
    text-decoration: underline;
  }
`;

const ActionRow = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.75rem;
`;

const ActionLink = styled.button`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0;
  transition: color 0.15s ease;

  &:hover {
    color: #6b3410;
    text-decoration: underline;
  }

  &::after {
    content: ' →';
  }
`;

const AnimatedContent = styled.div<{ $dir: 'left' | 'right' | null }>`
  ${props => props.$dir === 'left' && css`animation: ${slideLeft} 250ms ease;`}
  ${props => props.$dir === 'right' && css`animation: ${slideRight} 250ms ease;`}
`;

const SeeOriginalLink = styled.button`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0;
  margin-left: 0.5rem;
  vertical-align: middle;
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
  margin-top: 0.4rem;
`;

const PassageCard: React.FC<PassageCardProps> = ({
  passages,
  onBookmark,
  isBookmarked,
  onReadInContext,
  onSelectPassage,
  isDesktop = false,
}) => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [slideDir, setSlideDir] = useState<'left' | 'right' | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [measuredHeight, setMeasuredHeight] = useState<string>('5.6em');

  const passage = passages[currentIndex];

  const {
    showOriginal,
    toggleOriginal,
    displayText,
    showFrUnavailable,
    fetchingFr,
    canShowOriginalToggle,
    sourceLabel,
    loadFullText,
  } = usePassageText(passage, { includeCitation: true });

  // Lazy-load full text when a truncated passage is expanded
  useEffect(() => {
    if (expanded && passage.index != null && isPassageTruncated(passage)) {
      loadFullText(passage.index);
    }
  }, [expanded, passage, loadFullText]);

  const handleToggleOriginal = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    toggleOriginal();
  }, [toggleOriginal]);

  // Measure content for smooth expand
  useEffect(() => {
    if (expanded && contentRef.current) {
      const height = contentRef.current.scrollHeight;
      setMeasuredHeight(`${height}px`);
      // After transition, allow natural reflow
      const timer = setTimeout(() => setMeasuredHeight('none'), 360);
      return () => clearTimeout(timer);
    } else {
      setMeasuredHeight('5.6em');
    }
  }, [expanded, currentIndex]);

  const handleCardClick = useCallback(() => {
    if (isDesktop && onSelectPassage) {
      onSelectPassage(passage);
      return;
    }
    if (!expanded) {
      setExpanded(true);
    }
  }, [expanded, isDesktop, onSelectPassage, passage]);

  const handleCollapse = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded(false);
  }, []);

  const handleBookmarkClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onBookmark(passage);
  }, [onBookmark, passage]);

  const goTo = useCallback((index: number, direction: 'left' | 'right') => {
    setSlideDir(direction);
    setCurrentIndex(index);
    setTimeout(() => setSlideDir(null), 270);
  }, []);

  return (
    <CardWrapper
      $expanded={expanded}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleCardClick();
        }
      }}
    >
      <CardInner>
        <BookmarkIcon
          $active={isBookmarked(passage)}
          onClick={handleBookmarkClick}
          aria-label={isBookmarked(passage) ? t('passage.bookmarkRemove') : t('passage.bookmarkAdd')}
        >
          {isBookmarked(passage) ? '★' : '☆'}
        </BookmarkIcon>

        <AnimatedContent $dir={slideDir}>
          <SourceChip>{sourceLabel}</SourceChip>
          {canShowOriginalToggle && (
            <SeeOriginalLink onClick={handleToggleOriginal}>
              {showOriginal ? t('passage.seeTranslation') : t('passage.seeOriginal')}
            </SeeOriginalLink>
          )}

          <TextPreview
            ref={contentRef}
            $expanded={expanded}
            $maxHeight={expanded ? measuredHeight : '5.6em'}
          >
            {fetchingFr && showOriginal ? t('common.loading') : displayText}
          </TextPreview>

          {showFrUnavailable && (
            <UnavailableNote>{t('passage.frenchUnavailable')}</UnavailableNote>
          )}

          {passage.relevance_summary && (
            <RelevanceSummary>{passage.relevance_summary}</RelevanceSummary>
          )}
        </AnimatedContent>

        {expanded && (
          <ActionRow>
            <CollapseButton onClick={handleCollapse}>
              {t('common.collapse')}
            </CollapseButton>
            {onReadInContext && passage.index != null && (
              <ActionLink onClick={(e) => { e.stopPropagation(); onReadInContext(passage); }}>
                {t('passage.readInContext')}
              </ActionLink>
            )}
          </ActionRow>
        )}

        <PassageNav
          count={passages.length}
          currentIndex={currentIndex}
          onNavigate={(i, dir) => goTo(i, dir)}
          stopClickPropagation
        />
      </CardInner>
    </CardWrapper>
  );
};

export default PassageCard;
