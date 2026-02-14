import React, { useState, useRef, useEffect } from 'react';
import styled from 'styled-components';

interface Bookmark {
  id: string;
  text: string;
  book: string;
  chapter: string;
  index?: number;
  savedAt: string;
}

interface BookmarkDropdownProps {
  bookmarks: Bookmark[];
  onNavigate: (bookmark: Bookmark) => void;
}

const Wrapper = styled.div`
  position: relative;
`;

const TriggerButton = styled.button`
  background: none;
  border: none;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  color: #8b4513;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  transition: background 0.15s ease;
  white-space: nowrap;

  &:hover {
    background: rgba(139, 69, 19, 0.08);
  }
`;

const Dropdown = styled.div`
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 320px;
  max-height: 400px;
  overflow-y: auto;
  background: #faf8f5;
  border: 1px solid #d4ccc3;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  z-index: 100;
  padding: 0.5rem 0;

  scrollbar-width: thin;
  scrollbar-color: #d4ccc3 transparent;
  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: #d4ccc3; border-radius: 2px; }
`;

const DropdownHeader = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.75rem;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.4rem 0.75rem 0.3rem;
`;

const Item = styled.button<{ $disabled?: boolean }>`
  display: block;
  width: 100%;
  background: none;
  border: none;
  text-align: left;
  padding: 0.5rem 0.75rem;
  cursor: ${props => props.$disabled ? 'default' : 'pointer'};
  opacity: ${props => props.$disabled ? 0.5 : 1};
  transition: background 0.12s ease;

  &:hover {
    background: ${props => props.$disabled ? 'none' : 'rgba(139, 69, 19, 0.06)'};
  }
`;

const ItemSource = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.7rem;
  font-variant: small-caps;
  color: #8b4513;
  margin-bottom: 0.15rem;
`;

const ItemText = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.8rem;
  color: #555;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

const EmptyMessage = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.82rem;
  color: #aaa;
  padding: 1rem 0.75rem;
  text-align: center;
`;

const BookmarkDropdown: React.FC<BookmarkDropdownProps> = ({ bookmarks, onNavigate }) => {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const sorted = [...bookmarks].sort(
    (a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime()
  );

  return (
    <Wrapper ref={wrapperRef}>
      <TriggerButton onClick={() => setOpen(!open)} title="Saved passages">
        &#9733; {bookmarks.length > 0 && bookmarks.length}
      </TriggerButton>
      {open && (
        <Dropdown>
          <DropdownHeader>Saved Passages</DropdownHeader>
          {sorted.length === 0 ? (
            <EmptyMessage>No saved passages yet</EmptyMessage>
          ) : (
            sorted.map(bm => (
              <Item
                key={bm.id}
                $disabled={bm.index == null}
                onClick={() => {
                  if (bm.index != null) {
                    onNavigate(bm);
                    setOpen(false);
                  }
                }}
                title={bm.index == null ? 'Position unknown' : bm.text.slice(0, 200)}
              >
                <ItemSource>{bm.book} &mdash; {bm.chapter}</ItemSource>
                <ItemText>{bm.text}</ItemText>
              </Item>
            ))
          )}
        </Dropdown>
      )}
    </Wrapper>
  );
};

export default BookmarkDropdown;
