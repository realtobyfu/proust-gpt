import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import styled from 'styled-components';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useLanguage } from '../contexts/LanguageContext';
import { useReadingProgress } from '../hooks/useReadingProgress';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { formatPassageText } from '../utils/formatPassageText';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const PASSAGES_PER_PAGE = 20;

const Container = styled.div<{ $wide?: boolean }>`
  max-width: ${props => props.$wide ? '1200px' : '780px'};
  margin: 0 auto;
  padding: 1.5rem 1rem 2rem;
  position: relative;
  transition: max-width 0.3s ease;
`;

const ChapterTitle = styled.h2`
  font-family: 'Belgrano', serif;
  font-size: 1.6rem;
  color: #333;
  margin: 1rem 0 0.5rem;
  font-weight: 400;
`;

const VolumeName = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #8b4513;
`;

const ProgressBarContainer = styled.div`
  position: sticky;
  top: 0;
  z-index: 10;
  background: #f7f4f0;
  padding: 0;
`;

const ProgressLabel = styled.div`
  display: flex;
  justify-content: flex-end;
  padding: 0.2rem 1rem 0.15rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.7rem;
  color: #aaa;
`;

const ProgressTrack = styled.div`
  height: 3px;
  background: #e0d8cf;
`;

const ProgressFill = styled.div<{ $percent: number }>`
  height: 100%;
  width: ${props => props.$percent}%;
  background: #8b4513;
  transition: width 0.15s ease;
`;

const PassageBlock = styled.div`
  position: relative;
  margin-bottom: 0.6rem;

  &:hover .passage-actions {
    opacity: 1;
  }
`;

const PassageText = styled.p`
  font-family: 'Georgia', serif;
  font-size: 1.15rem;
  line-height: 1.95;
  color: #333;
  text-align: justify;
  margin: 0;
  padding: 0.5rem 0;
`;

const ParagraphNumber = styled.span`
  position: absolute;
  left: -2.5rem;
  top: 0.55rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.65rem;
  color: #ccc;
  user-select: none;

  @media (max-width: 768px) {
    display: none;
  }
`;

const Divider = styled.div`
  text-align: center;
  color: #d4ccc3;
  font-size: 0.8rem;
  letter-spacing: 0.5em;
  padding: 0.8rem 0;
  user-select: none;
`;

const PassageActions = styled.div`
  position: absolute;
  left: calc(100% + 0.5rem);
  top: 0.3rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  opacity: 0;
  transition: opacity 0.15s ease;
  white-space: nowrap;

  @media (max-width: 768px) {
    opacity: 1;
    position: static;
    flex-direction: row;
    justify-content: flex-end;
    margin-top: 0.25rem;
  }
`;

const ActionButton = styled.button<{ $active?: boolean }>`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.75rem;
  color: ${props => props.$active ? '#8b4513' : '#bbb'};
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  transition: color 0.15s ease;

  &:hover {
    color: #8b4513;
    background: rgba(139, 69, 19, 0.06);
  }
`;

const HeaderRow = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  position: relative;
`;

const PageInfo = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.78rem;
  color: #999;
`;

const SideArrow = styled.button<{ $side: 'left' | 'right'; $visible: boolean }>`
  position: fixed;
  bottom: 3rem;
  ${props => props.$side === 'left' ? 'left: calc(50% - 540px)' : 'right: calc(50% - 540px)'};
  background: none;
  border: none;
  padding: 0.5rem;
  color: #8b4513;
  cursor: pointer;
  font-size: 2.2rem;
  line-height: 1;
  z-index: 15;
  opacity: ${props => props.$visible ? 1 : 0};
  pointer-events: ${props => props.$visible ? 'auto' : 'none'};
  transition: color 0.15s, opacity 0.3s ease;

  &:hover {
    color: #6b3410;
  }

  &:disabled {
    color: #d4ccc3;
    cursor: default;
  }

  @media (max-width: 1100px) {
    ${props => props.$side === 'left' ? 'left: 1rem' : 'right: 1rem'};
  }

  @media (max-width: 900px) {
    display: none;
  }
`;

const BackButton = styled.button`
  position: absolute;
  right: calc(100% + 1rem);
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: none;
  border: none;
  padding: 0.2rem 0;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #999;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s ease;

  &:hover {
    color: #8b4513;
  }

  @media (max-width: 1024px) {
    position: static;
    transform: none;
  }
`;

const LoadingState = styled.div`
  text-align: center;
  padding: 2rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  color: #999;
`;

interface Passage {
  book: string;
  chapter: string;
  text: string;
  text_fr?: string;
  text_unavailable?: boolean;
  volume: number;
  index: number;
}

interface ChapterNav {
  volume: number;
  chapter: string;
}

interface Bookmark {
  id: string;
  text: string;
  book: string;
  chapter: string;
  index?: number;
  savedAt: string;
}

interface ReadingViewProps {
  volume: number;
  chapter: string;
  page: number;
  onNavigateToToc: () => void;
  highlightPassageIndex?: number;
}

const UnavailableNote = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.8rem;
  color: #999;
  font-style: italic;
  display: block;
  margin-top: 0.25rem;
`;

const BilingualToggle = styled.button<{ $active: boolean }>`
  background: none;
  border: 1px solid ${props => props.$active ? '#8b4513' : '#d4ccc3'};
  border-radius: 4px;
  padding: 0.2rem 0.5rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.7rem;
  color: ${props => props.$active ? '#8b4513' : '#aaa'};
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;

  &:hover {
    color: #8b4513;
    border-color: #8b4513;
  }
`;

const BilingualRow = styled.div`
  display: flex;
  gap: 2rem;

  @media (max-width: 768px) {
    flex-direction: column;
    gap: 0;
  }
`;

const BilingualColumn = styled.div<{ $secondary?: boolean }>`
  flex: ${props => props.$secondary ? '0 0 43%' : '1'};
  min-width: 0;

  ${props => props.$secondary && `
    border-left: 1px solid #e8e2da;
    padding-left: 2rem;

    @media (max-width: 768px) {
      border-left: none;
      padding-left: 0;
      border-top: 1px solid #e8e2da;
      padding-top: 0.25rem;
    }
  `}
`;

const SecondaryPassageText = styled.p`
  font-family: 'Georgia', serif;
  font-size: 1.08rem;
  line-height: 1.9;
  color: #666;
  text-align: justify;
  margin: 0;
  padding: 0.5rem 0;
`;

const ReadingView: React.FC<ReadingViewProps> = ({ volume, chapter, page, onNavigateToToc, highlightPassageIndex }) => {
  const { t } = useTranslation();
  const { textLanguage } = useLanguage();
  const navigate = useNavigate();
  const { setPageProgress } = useReadingProgress();
  const [bookmarks, setBookmarks] = useLocalStorage<Bookmark[]>('proust-bookmarks', []);

  const [passages, setPassages] = useState<Passage[]>([]);
  const [totalInChapter, setTotalInChapter] = useState(0);
  const [volumeName, setVolumeName] = useState('');
  const [chapterName, setChapterName] = useState('');
  const [, setVolumeNameEn] = useState('');
  const [chapterNameEn, setChapterNameEn] = useState('');
  const [prevChapter, setPrevChapter] = useState<ChapterNav | null>(null);
  const [nextChapter, setNextChapter] = useState<ChapterNav | null>(null);
  const [loading, setLoading] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);
  const [atBottom, setAtBottom] = useState(false);
  const [bilingual, setBilingual] = useLocalStorage<boolean>('proust-bilingual', false);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const totalPages = Math.max(1, Math.ceil(totalInChapter / PASSAGES_PER_PAGE));
  const isFirstPage = page === 0;
  const isLastPage = page >= totalPages - 1;

  const fetchPassages = useCallback(async (vol: number, ch: string, pageNum: number, lang: string) => {
    setLoading(true);
    try {
      const offset = pageNum * PASSAGES_PER_PAGE;
      const params = new URLSearchParams({
        volume: vol.toString(),
        chapter: ch,
        offset: offset.toString(),
        limit: PASSAGES_PER_PAGE.toString(),
        lang,
      });
      const res = await fetch(`${API_BASE_URL}/api/read/chapter?${params}`);
      const data = await res.json();

      if (data.error) {
        console.error('Chapter not found:', data.error);
        return;
      }

      setPassages(data.passages);
      setTotalInChapter(data.total_in_chapter);
      setVolumeName(data.volume_name);
      setChapterName(data.chapter_name);
      setVolumeNameEn(data.volume_name_en || '');
      setChapterNameEn(data.chapter_name_en || '');
      setPrevChapter(data.prev_chapter);
      setNextChapter(data.next_chapter);
    } catch (err) {
      console.error('Failed to fetch passages:', err);
    } finally {
      setLoading(false);
      setInitialLoad(false);
    }
  }, []);

  // Fetch passages when volume/chapter/page/language changes
  useEffect(() => {
    setInitialLoad(true);
    const lang = bilingual ? 'both' : textLanguage;
    fetchPassages(volume, chapter, page, lang);
    if (highlightPassageIndex == null) {
      window.scrollTo(0, 0);
    }
  }, [volume, chapter, page, textLanguage, bilingual, fetchPassages, highlightPassageIndex]);

  // Track reading progress — single atomic update per page load
  useEffect(() => {
    if (passages.length === 0) return;
    setPageProgress(volume, chapter, passages[0].index, page, passages.map(p => p.index));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [passages]);

  // Scroll to and highlight the target passage when navigating from chat
  useEffect(() => {
    if (highlightPassageIndex == null || passages.length === 0 || !containerRef.current) return;

    const blocks = containerRef.current.querySelectorAll<HTMLElement>('[data-passage-indices]');
    let targetBlock: HTMLElement | null = null;

    blocks.forEach(block => {
      const indices = block.dataset.passageIndices?.split(',').map(Number) || [];
      if (indices.includes(highlightPassageIndex)) {
        targetBlock = block;
      }
    });

    if (targetBlock) {
      // Scroll to the block
      setTimeout(() => {
        targetBlock!.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Apply highlight
        targetBlock!.style.borderLeft = '3px solid #8b4513';
        targetBlock!.style.background = 'rgba(139, 69, 19, 0.06)';
        targetBlock!.style.paddingLeft = '0.75rem';
        targetBlock!.style.transition = 'all 0.3s ease';

        // Fade out after 3 seconds
        setTimeout(() => {
          if (targetBlock) {
            targetBlock.style.borderLeft = '';
            targetBlock.style.background = '';
            targetBlock.style.paddingLeft = '';
          }
        }, 3000);
      }, 100);
    }
  }, [highlightPassageIndex, passages]);

  // Show navigation arrows only when scrolled near the bottom
  useEffect(() => {
    const handleScroll = () => {
      const scrollBottom = window.innerHeight + window.scrollY;
      const threshold = document.documentElement.scrollHeight - 150;
      setAtBottom(scrollBottom >= threshold);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Merge consecutive chunks that belong to the same paragraph
  const mergedPassages = useMemo(() => {
    if (passages.length === 0) return [];

    const groups: Passage[][] = [];
    let currentGroup: Passage[] = [passages[0]];

    for (let i = 1; i < passages.length; i++) {
      const prev = currentGroup[currentGroup.length - 1];
      const curr = passages[i];
      const prevText = prev.text.trim();

      // Merge if consecutive indices and previous doesn't end with sentence-ending punctuation
      if (
        prev.index + 1 === curr.index &&
        !prevText.match(/[.!?]["'\u201D\u2019)]*\s*$/)
      ) {
        currentGroup.push(curr);
      } else {
        groups.push(currentGroup);
        currentGroup = [curr];
      }
    }
    groups.push(currentGroup);

    return groups;
  }, [passages]);

  const progressPercent = () => {
    if (totalPages <= 1) return 100;
    return Math.round(((page + 1) / totalPages) * 100);
  };

  const handleBookmark = (text: string, passage: Passage) => {
    const existing = bookmarks.find(b => b.text === text);
    if (existing) {
      setBookmarks(bookmarks.filter(b => b.text !== text));
    } else {
      setBookmarks([...bookmarks, {
        id: Date.now().toString(),
        text,
        book: passage.book,
        chapter: passage.chapter,
        index: passage.index,
        savedAt: new Date().toISOString(),
      }]);
    }
  };

  const isBookmarked = (text: string) => bookmarks.some(b => b.text === text);

  const handleExplore = (text: string, passage: Passage) => {
    const snippet = text.slice(0, 120);
    navigate('/chat', {
      state: {
        mode: 'explore_lost_time',
        prompt: `Tell me more about this passage from ${passage.book}, ${passage.chapter}: "${snippet}..."`,
      },
    });
  };

  const handlePageNav = (newPage: number) => {
    const params = new URLSearchParams({
      volume: volume.toString(),
      chapter,
      page: newPage.toString(),
    });
    window.history.pushState({}, '', `/read?${params}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const handleChapterNav = (nav: ChapterNav | null) => {
    if (!nav) return;
    const params = new URLSearchParams({
      volume: nav.volume.toString(),
      chapter: nav.chapter,
    });
    window.history.pushState({}, '', `/read?${params}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  if (initialLoad) {
    return (
      <Container>
        <LoadingState>{t('readPage.loadingChapter')}</LoadingState>
      </Container>
    );
  }

  return (
    <>
      <ProgressBarContainer>
        <ProgressTrack>
          <ProgressFill $percent={progressPercent()} />
        </ProgressTrack>
        {totalPages > 1 && (
          <ProgressLabel>{page + 1} / {totalPages}</ProgressLabel>
        )}
      </ProgressBarContainer>

      <Container ref={containerRef} $wide={bilingual}>
        <HeaderRow>
          <BackButton onClick={onNavigateToToc}>&larr;{!bilingual && ` ${t('readPage.contents')}`}</BackButton>
          <VolumeName>{volumeName}</VolumeName>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BilingualToggle
              $active={bilingual}
              onClick={() => setBilingual(!bilingual)}
              title={bilingual ? 'Hide translation' : 'Show side-by-side translation'}
            >
              {bilingual ? 'EN / FR' : 'EN / FR'}
            </BilingualToggle>
            {totalPages > 1 && <PageInfo>{t('readPage.pageOf', { current: page + 1, total: totalPages })}</PageInfo>}
          </div>
        </HeaderRow>
        {page === 0 && (
          bilingual ? (
            <BilingualRow>
              <BilingualColumn>
                <ChapterTitle>{chapterName}</ChapterTitle>
              </BilingualColumn>
              <BilingualColumn $secondary>
                <ChapterTitle style={{ color: '#666' }}>{chapterNameEn || chapterName}</ChapterTitle>
              </BilingualColumn>
            </BilingualRow>
          ) : (
            <ChapterTitle>{chapterName}</ChapterTitle>
          )
        )}

        {mergedPassages.map((group, gi) => {
          const mergedText = group.map(p => p.text.trim()).join(' ');
          const firstPassage = group[0];

          return (
            <React.Fragment key={`group-${firstPassage.index}`}>
              <PassageBlock data-passage-indices={group.map(p => p.index).join(',')}>
                <ParagraphNumber>{gi + 1}</ParagraphNumber>
                {bilingual ? (() => {
                  const frText = group.map(p => (p.text_fr || '').trim()).filter(Boolean).join(' ');
                  return (
                    <BilingualRow>
                      <BilingualColumn>
                        {frText
                          ? <PassageText>{formatPassageText(frText)}</PassageText>
                          : <UnavailableNote>{t('passage.frenchUnavailable')}</UnavailableNote>
                        }
                      </BilingualColumn>
                      <BilingualColumn $secondary>
                        <SecondaryPassageText>{formatPassageText(mergedText)}</SecondaryPassageText>
                      </BilingualColumn>
                    </BilingualRow>
                  );
                })() : (
                  <>
                    <PassageText>{formatPassageText(mergedText)}</PassageText>
                    {textLanguage === 'fr' && group.some(p => p.text_unavailable) && (
                      <UnavailableNote>{t('passage.frenchUnavailable')}</UnavailableNote>
                    )}
                  </>
                )}
                <PassageActions className="passage-actions">
                  <ActionButton
                    $active={isBookmarked(mergedText)}
                    onClick={() => handleBookmark(mergedText, firstPassage)}
                    title={isBookmarked(mergedText) ? t('passage.bookmarkRemove') : t('passage.bookmarkAdd')}
                  >
                    {isBookmarked(mergedText) ? t('common.saved') : t('common.save')}
                  </ActionButton>
                  <ActionButton onClick={() => handleExplore(mergedText, firstPassage)} title={t('common.explore')}>
                    {t('common.explore')}
                  </ActionButton>
                </PassageActions>
              </PassageBlock>
              {gi < mergedPassages.length - 1 && (gi + 1) % 5 === 0 && (
                <Divider>...</Divider>
              )}
            </React.Fragment>
          );
        })}

        {!loading && passages.length === 0 && (
          <LoadingState>{t('readPage.noPassages')}</LoadingState>
        )}
      </Container>

      {isFirstPage ? (
        prevChapter && (
          <SideArrow $side="left" $visible={atBottom} onClick={() => handleChapterNav(prevChapter)} aria-label="Previous chapter">
            &#8249;
          </SideArrow>
        )
      ) : (
        <SideArrow $side="left" $visible={atBottom} onClick={() => handlePageNav(page - 1)} aria-label="Previous page">
          &#8249;
        </SideArrow>
      )}

      {isLastPage ? (
        nextChapter && (
          <SideArrow $side="right" $visible={atBottom} onClick={() => handleChapterNav(nextChapter)} aria-label="Next chapter">
            &#8250;
          </SideArrow>
        )
      ) : (
        <SideArrow $side="right" $visible={atBottom} onClick={() => handlePageNav(page + 1)} aria-label="Next page">
          &#8250;
        </SideArrow>
      )}
    </>
  );
};

export default ReadingView;
