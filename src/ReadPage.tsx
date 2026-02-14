import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import styled from 'styled-components';
import TableOfContents from './components/TableOfContents';
import ReadingView from './components/ReadingView';
import BookmarkDropdown from './components/BookmarkDropdown';
import { useReadingProgress } from './hooks/useReadingProgress';
import { useLocalStorage } from './hooks/useLocalStorage';

const API_BASE_URL = 'http://127.0.0.1:5000';

interface Bookmark {
  id: string;
  text: string;
  book: string;
  chapter: string;
  index?: number;
  savedAt: string;
}

const PageContainer = styled.div`
  background-color: #f7f4f0;
  min-height: 100vh;
  color: #333;
`;

const Header = styled.div`
  background-color: #faf8f5;
  border-bottom: 1px solid #e0d8cf;
  padding: 1.25rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const Breadcrumb = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 1rem;
  color: #666;

  a {
    color: #8b4513;
    text-decoration: none;
    font-family: 'Belgrano', serif;
    font-weight: 400;

    &:hover {
      text-decoration: underline;
    }
  }
`;

const BreadcrumbSep = styled.span`
  margin: 0 0.4rem;
  color: #ccc;
`;

const ChapterLink = styled.button`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 1rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
`;

const HeaderLinks = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;

  a {
    color: #8b4513;
    text-decoration: underline;
  }
`;

const TocHeader = styled.div`
  max-width: 720px;
  margin: 0 auto;
  padding: 2.5rem 1.5rem 0;
`;

const Title = styled.h1`
  font-family: 'Belgrano', serif;
  font-size: 2rem;
  font-weight: 400;
  color: #333;
  margin: 0 0 0.5rem;
`;

const Subtitle = styled.p`
  font-family: 'Georgia', serif;
  font-size: 1rem;
  color: #777;
  margin: 0 0 1rem;
  line-height: 1.6;
`;

const ContinueBanner = styled.button`
  max-width: 360px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: rgba(139, 69, 19, 0.04);
  border: 1px solid #d4ccc3;
  border-radius: 8px;
  padding: 0.7rem 1rem;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, background 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.07);
    border-color: #b8a48e;
  }
`;

const ContinueIcon = styled.div`
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: rgba(139, 69, 19, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #8b4513;
  font-size: 0.75rem;
`;

const ContinueTextGroup = styled.div`
  flex: 1;
  min-width: 0;
`;

const ContinueTitle = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #8b4513;
  font-weight: 600;
  margin-bottom: 0.15rem;
`;

const ContinueDetail = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.78rem;
  color: #777;
`;

const LoadingContainer = styled.div`
  text-align: center;
  padding: 4rem 2rem;
  font-family: 'IBM Plex Sans', sans-serif;
  color: #999;
`;

interface Volume {
  volume: number;
  volume_name: string;
  chapter_count: number;
  total_passages: number;
  chapters: {
    name: string;
    passage_count: number;
    first_index: number;
    last_index: number;
  }[];
}

const ReadPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [volumes, setVolumes] = useState<Volume[]>([]);
  const [loading, setLoading] = useState(true);
  const { lastPosition } = useReadingProgress();
  const [bookmarks] = useLocalStorage<Bookmark[]>('proust-bookmarks', []);

  // Read current view from URL params
  const currentVolume = searchParams.get('volume');
  const currentChapter = searchParams.get('chapter');
  const currentPage = parseInt(searchParams.get('page') || '0', 10);
  const passageIndexParam = searchParams.get('passageIndex');
  const highlightPassageIndex = passageIndexParam != null ? parseInt(passageIndexParam, 10) : undefined;
  const isChapterView = currentVolume && currentChapter;

  // Fetch TOC
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/read/toc`)
      .then(res => res.json())
      .then(data => {
        setVolumes(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch TOC:', err);
        setLoading(false);
      });
  }, []);

  // Listen for popstate events (from ReadingView chapter navigation)
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      setSearchParams(params, { replace: true });
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [setSearchParams]);

  const handleSelectChapter = useCallback((volume: number, chapter: string) => {
    setSearchParams({ volume: volume.toString(), chapter });
  }, [setSearchParams]);

  const handleBackToToc = useCallback(() => {
    setSearchParams({});
  }, [setSearchParams]);

  const handleContinueReading = () => {
    if (lastPosition) {
      const params: Record<string, string> = {
        volume: lastPosition.volume.toString(),
        chapter: lastPosition.chapter,
      };
      if (lastPosition.page && lastPosition.page > 0) {
        params.page = lastPosition.page.toString();
      }
      setSearchParams(params);
    }
  };

  const handleNavigateToBookmark = useCallback(async (bookmark: Bookmark) => {
    if (bookmark.index == null) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/read/locate?index=${bookmark.index}`);
      const data = await res.json();
      if (data.error) {
        console.error('Failed to locate passage:', data.error);
        return;
      }
      setSearchParams({
        volume: data.volume.toString(),
        chapter: data.chapter,
        page: data.page.toString(),
        passageIndex: data.passageIndex.toString(),
      });
    } catch (err) {
      console.error('Failed to locate passage:', err);
    }
  }, [setSearchParams]);

  // Find volume name for breadcrumb
  const getVolumeName = () => {
    if (!currentVolume) return '';
    const vol = volumes.find(v => v.volume === Number(currentVolume));
    return vol?.volume_name || '';
  };

  if (loading) {
    return (
      <PageContainer>
        <Header>
          <Breadcrumb>
            <Link to="/">Proust GPT</Link>
            <BreadcrumbSep>&gt;</BreadcrumbSep>
            Read
          </Breadcrumb>
        </Header>
        <LoadingContainer>Loading table of contents...</LoadingContainer>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Header>
        <Breadcrumb>
          <Link to="/">Proust GPT</Link>
          <BreadcrumbSep>&gt;</BreadcrumbSep>
          {isChapterView ? (
            <>
              <ChapterLink onClick={handleBackToToc}>Read</ChapterLink>
              <BreadcrumbSep>&gt;</BreadcrumbSep>
              {getVolumeName()}
              <BreadcrumbSep>&gt;</BreadcrumbSep>
              {currentChapter}
            </>
          ) : (
            'Read'
          )}
        </Breadcrumb>
        <HeaderLinks>
          <BookmarkDropdown
            bookmarks={bookmarks}
            onNavigate={handleNavigateToBookmark}
          />
          <Link to="/chat">Chat</Link>
          <Link to="/about">About</Link>
        </HeaderLinks>
      </Header>

      {isChapterView ? (
        <ReadingView
          volume={Number(currentVolume)}
          chapter={currentChapter}
          page={currentPage}
          onNavigateToToc={handleBackToToc}
          highlightPassageIndex={highlightPassageIndex}
        />
      ) : (
        <>
          <TocHeader>
            <Title>In Search of Lost Time</Title>
            <Subtitle>
              Seven volumes, {volumes.reduce((sum, v) => sum + v.total_passages, 0).toLocaleString()} passages.
              Browse the complete text of Marcel Proust's masterwork.
            </Subtitle>
          </TocHeader>

          {lastPosition && (
            <div style={{ maxWidth: '720px', margin: '0 auto', padding: '0 1.5rem', display: 'flex' }}>
              <ContinueBanner onClick={handleContinueReading}>
                <ContinueIcon>&#9654;</ContinueIcon>
                <ContinueTextGroup>
                  <ContinueTitle>Continue reading</ContinueTitle>
                  <ContinueDetail>
                    {volumes.find(v => v.volume === lastPosition.volume)?.volume_name || `Volume ${lastPosition.volume}`}
                    {' \u2014 '}
                    {lastPosition.chapter}
                  </ContinueDetail>
                </ContinueTextGroup>
              </ContinueBanner>
            </div>
          )}

          <TableOfContents
            volumes={volumes}
            onSelectChapter={handleSelectChapter}
          />
        </>
      )}
    </PageContainer>
  );
};

export default ReadPage;
