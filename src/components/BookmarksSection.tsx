import React, { useState } from 'react';
import styled from 'styled-components';

interface Bookmark {
  id: string;
  text: string;
  book: string;
  chapter: string;
  index?: number;
  savedAt: string;
}

interface BookmarksSectionProps {
  bookmarks: Bookmark[];
  onNavigate: (bookmark: Bookmark) => void;
  onRemove: (bookmark: Bookmark) => void;
  onExploreInChat: (bookmark: Bookmark) => void;
}

const Section = styled.div`
  max-width: 720px;
  margin: 0 auto;
  padding: 1rem 1.5rem 0;
`;

const SectionTitle = styled.h3`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #8b4513;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.6rem;
`;

const CardList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
`;

const Card = styled.div`
  background: rgba(139, 69, 19, 0.04);
  border: 1px solid #d4ccc3;
  border-radius: 8px;
  padding: 0.7rem 1rem;
  transition: border-color 0.2s ease, background 0.2s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.07);
    border-color: #b8a48e;
  }

  &:hover .card-actions {
    opacity: 1;
  }
`;

const SourceLabel = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  font-variant: small-caps;
  color: #8b4513;
  margin-bottom: 0.3rem;
`;

const TextPreview = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.88rem;
  color: #555;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

const CardActions = styled.div`
  display: flex;
  gap: 0.75rem;
  margin-top: 0.4rem;
  opacity: 0;
  transition: opacity 0.15s ease;
`;

const ActionLink = styled.button<{ $danger?: boolean }>`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.75rem;
  color: ${props => props.$danger ? '#a06050' : '#8b4513'};
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-decoration-color: transparent;
  transition: text-decoration-color 0.15s ease;

  &:hover {
    text-decoration-color: currentColor;
  }

  &:disabled {
    color: #ccc;
    cursor: default;
    text-decoration: none;
  }
`;

const ShowAllButton = styled.button`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.8rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0.4rem 0 0;
  text-decoration: underline;
  text-decoration-color: transparent;
  transition: text-decoration-color 0.15s ease;

  &:hover {
    text-decoration-color: currentColor;
  }
`;

const COLLAPSED_COUNT = 4;

const BookmarksSection: React.FC<BookmarksSectionProps> = ({
  bookmarks,
  onNavigate,
  onRemove,
  onExploreInChat,
}) => {
  const [expanded, setExpanded] = useState(false);

  // Sort most recently saved first
  const sorted = [...bookmarks].sort(
    (a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime()
  );

  const visible = expanded ? sorted : sorted.slice(0, COLLAPSED_COUNT);
  const hasMore = sorted.length > COLLAPSED_COUNT;

  return (
    <Section>
      <SectionTitle>Saved Passages ({bookmarks.length})</SectionTitle>
      <CardList>
        {visible.map(bm => (
          <Card key={bm.id}>
            <SourceLabel>{bm.book} &mdash; {bm.chapter}</SourceLabel>
            <TextPreview>{bm.text}</TextPreview>
            <CardActions className="card-actions">
              <ActionLink
                onClick={() => onNavigate(bm)}
                disabled={bm.index == null}
                title={bm.index == null ? 'Position unknown' : 'Navigate to this passage'}
              >
                Read in context
              </ActionLink>
              <ActionLink onClick={() => onExploreInChat(bm)}>
                Explore in Chat
              </ActionLink>
              <ActionLink $danger onClick={() => onRemove(bm)}>
                Remove
              </ActionLink>
            </CardActions>
          </Card>
        ))}
      </CardList>
      {hasMore && (
        <ShowAllButton onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show fewer' : `Show all ${sorted.length} passages`}
        </ShowAllButton>
      )}
    </Section>
  );
};

export default BookmarksSection;
