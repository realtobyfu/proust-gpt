import React, { useState } from 'react';
import styled, { css } from 'styled-components';

const PassageContainer = styled.div<{ $clickable: boolean }>`
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 10px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  max-width: 100%;
  color: #333;
  transition: all 0.2s ease;

  &:hover {
    background-color: rgba(255, 255, 255, 0.9);
  }

  ${props => props.$clickable && css`
    cursor: pointer;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
  `}
`;

const PassageTextWrapper = styled.div<{ $truncated: boolean }>`
  position: relative;

  ${props => props.$truncated && css`
    max-height: 5.6em; /* ~3 lines at 1.8 line-height */
    overflow: hidden;

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

const PassageText = styled.p`
  font-family: 'Georgia', serif;
  font-size: 1.05rem;
  line-height: 1.8;
  margin: 0 0 1rem 0;
`;

const PassageMetadata = styled.div`
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 0.5rem;
  font-style: italic;
`;

const ContextLink = styled.button`
  background: none;
  border: none;
  color: #8b4513;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.85rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  margin-right: 1rem;
  transition: color 0.2s ease;

  &:hover {
    color: #6b3410;
  }
`;

const ContextPanel = styled.div<{ $visible: boolean }>`
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e0e0e0;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.9rem;
  color: #555;
  line-height: 1.6;
  display: ${props => props.$visible ? 'block' : 'none'};
`;

const ContextSection = styled.div`
  margin-bottom: 0.8rem;

  &:last-child {
    margin-bottom: 0;
  }
`;

const ContextLabel = styled.span`
  font-weight: 500;
  color: #333;
`;

const ActionLinks = styled.div`
  margin-top: 1rem;
  display: flex;
  gap: 1rem;
  font-family: 'IBM Plex Sans', serif;
  font-size: 0.85rem;
`;

const ReadMoreHint = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.8rem;
  color: #8b4513;
  margin-top: 0.25rem;
`;

interface PassageProps {
  text: string;
  volume?: string;
  page?: number;
  narrativeContext?: string;
  characters?: string[];
  onBookmark?: () => void;
  isBookmarked?: boolean;
  onClick?: () => void;
  truncated?: boolean;
}

const PassageDisplay: React.FC<PassageProps> = ({
  text,
  volume = "In Search of Lost Time",
  page,
  narrativeContext,
  characters = [],
  onBookmark,
  isBookmarked = false,
  onClick,
  truncated = true,
}) => {
  const [showContext, setShowContext] = useState(false);

  const isTruncatedMode = truncated && !!onClick;

  return (
    <PassageContainer $clickable={!!onClick} onClick={onClick}>
      {(volume || page) && (
        <PassageMetadata>
          {volume && `From ${volume}`}
          {volume && page && ', '}
          {page && `p. ${page}`}
        </PassageMetadata>
      )}

      <PassageTextWrapper $truncated={isTruncatedMode}>
        <PassageText>{text}</PassageText>
      </PassageTextWrapper>

      {isTruncatedMode && (
        <ReadMoreHint>Read full passage</ReadMoreHint>
      )}

      {!isTruncatedMode && (
        <>
          <ActionLinks>
            <ContextLink onClick={(e) => { e.stopPropagation(); setShowContext(!showContext); }}>
              {showContext ? 'Hide context' : 'See context'}
            </ContextLink>
            {onBookmark && (
              <ContextLink
                onClick={(e) => { e.stopPropagation(); onBookmark(); }}
                style={isBookmarked ? { color: '#8b4513', fontWeight: 600 } : undefined}
              >
                {isBookmarked ? 'Saved' : 'Mark this passage'}
              </ContextLink>
            )}
          </ActionLinks>

          <ContextPanel $visible={showContext}>
            {narrativeContext && (
              <ContextSection>
                <ContextLabel>Context: </ContextLabel>
                {narrativeContext}
              </ContextSection>
            )}

            {characters.length > 0 && (
              <ContextSection>
                <ContextLabel>Characters: </ContextLabel>
                {characters.join(', ')}
              </ContextSection>
            )}
          </ContextPanel>
        </>
      )}
    </PassageContainer>
  );
};

export default PassageDisplay;
