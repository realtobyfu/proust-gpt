import React, { useState } from 'react';
import styled from 'styled-components';
import { theme } from '../styles/theme';

const PassageContainer = styled.div`
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all ${theme.transitions.default};
  
  &:hover {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  }
`;

const PassageHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(139, 69, 19, 0.1);
`;

const VolumeInfo = styled.div`
  flex: 1;
`;

const VolumeTitle = styled.h3`
  font-family: ${theme.fonts.heading};
  font-size: 1.2rem;
  color: ${theme.colors.primary};
  margin: 0 0 0.5rem 0;
`;

const ChapterInfo = styled.p`
  font-size: 0.9rem;
  color: ${theme.colors.textLight};
  margin: 0;
`;

const PageNumber = styled.span`
  font-size: 0.85rem;
  color: ${theme.colors.textLight};
  background: rgba(139, 69, 19, 0.1);
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
`;

const PassageText = styled.div`
  font-family: ${theme.fonts.primary};
  font-size: 1.1rem;
  line-height: 1.8;
  color: ${theme.colors.text};
  margin-bottom: 2rem;
  
  p {
    margin-bottom: 1rem;
    
    &:last-child {
      margin-bottom: 0;
    }
  }
  
  .highlight {
    background: rgba(232, 176, 75, 0.3);
    padding: 0.1rem 0.2rem;
    border-radius: 2px;
  }
`;

const ContextSection = styled.div`
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(139, 69, 19, 0.1);
`;

const ContextTitle = styled.h4`
  font-family: ${theme.fonts.secondary};
  font-size: 1rem;
  color: ${theme.colors.text};
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const ContextGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
`;

const ContextCard = styled.div`
  background: rgba(247, 244, 240, 0.8);
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid rgba(139, 69, 19, 0.1);
`;

const ContextLabel = styled.p`
  font-size: 0.85rem;
  color: ${theme.colors.textLight};
  margin: 0 0 0.25rem 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const ContextValue = styled.p`
  font-size: 0.95rem;
  color: ${theme.colors.text};
  margin: 0;
  font-weight: 500;
`;

const ThemeTagsContainer = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
`;

const ThemeTag = styled.span<{ color?: string }>`
  background: ${props => props.color || theme.colors.primary};
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 16px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }
`;

const RelatedPassagesSection = styled.div`
  margin-top: 1.5rem;
`;

const RelatedPassageLink = styled.button`
  display: block;
  width: 100%;
  text-align: left;
  background: rgba(139, 69, 19, 0.05);
  border: 1px solid rgba(139, 69, 19, 0.1);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  
  &:hover {
    background: rgba(139, 69, 19, 0.1);
    transform: translateX(4px);
  }
`;

const ActionBar = styled.div`
  display: flex;
  gap: 1rem;
  margin-top: 1.5rem;
`;

const ActionButton = styled.button`
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  background: transparent;
  border: 1px solid ${theme.colors.border};
  border-radius: 8px;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  display: flex;
  align-items: center;
  gap: 0.5rem;
  
  &:hover {
    background: rgba(139, 69, 19, 0.05);
    border-color: ${theme.colors.primary};
  }
`;

interface EnhancedPassage {
  text: string;
  volume: string;
  volumeNumber: number;
  chapter: string;
  page: number;
  narrativeContext: string;
  characters: string[];
  themes: { name: string; color: string }[];
  literaryDevices: string[];
  relatedPassages: { id: string; title: string; similarity: number }[];
  readingTime: number;
}

interface EnhancedPassageDisplayProps {
  passage: EnhancedPassage;
  searchTerms?: string[];
  onRelatedPassageClick?: (passageId: string) => void;
  onThemeClick?: (theme: string) => void;
}

const EnhancedPassageDisplay: React.FC<EnhancedPassageDisplayProps> = ({
  passage,
  searchTerms = [],
  onRelatedPassageClick,
  onThemeClick
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const highlightText = (text: string) => {
    if (searchTerms.length === 0) return text;
    
    let highlightedText = text;
    searchTerms.forEach(term => {
      const regex = new RegExp(`(${term})`, 'gi');
      highlightedText = highlightedText.replace(regex, '<span class="highlight">$1</span>');
    });
    
    return <span dangerouslySetInnerHTML={{ __html: highlightedText }} />;
  };

  return (
    <PassageContainer>
      <PassageHeader>
        <VolumeInfo>
          <VolumeTitle>Volume {passage.volumeNumber}: {passage.volume}</VolumeTitle>
          <ChapterInfo>{passage.chapter}</ChapterInfo>
        </VolumeInfo>
        <PageNumber>p. {passage.page}</PageNumber>
      </PassageHeader>

      <PassageText>
        <p>{highlightText(passage.text)}</p>
      </PassageText>

      <ContextSection>
        <ContextTitle>
          📚 Narrative Context
        </ContextTitle>
        <p style={{ color: theme.colors.textLight, lineHeight: 1.6 }}>
          {passage.narrativeContext}
        </p>
      </ContextSection>

      <ContextGrid>
        <ContextCard>
          <ContextLabel>Characters Present</ContextLabel>
          <ContextValue>{passage.characters.join(', ')}</ContextValue>
        </ContextCard>
        
        <ContextCard>
          <ContextLabel>Literary Devices</ContextLabel>
          <ContextValue>{passage.literaryDevices.join(', ')}</ContextValue>
        </ContextCard>
        
        <ContextCard>
          <ContextLabel>Reading Time</ContextLabel>
          <ContextValue>{passage.readingTime} minutes</ContextValue>
        </ContextCard>
      </ContextGrid>

      <ThemeTagsContainer>
        {passage.themes.map(theme => (
          <ThemeTag 
            key={theme.name}
            color={theme.color}
            onClick={() => onThemeClick?.(theme.name)}
          >
            {theme.name}
          </ThemeTag>
        ))}
      </ThemeTagsContainer>

      {isExpanded && (
        <RelatedPassagesSection>
          <ContextTitle>
            🔗 Related Passages
          </ContextTitle>
          {passage.relatedPassages.map(related => (
            <RelatedPassageLink
              key={related.id}
              onClick={() => onRelatedPassageClick?.(related.id)}
            >
              {related.title} ({Math.round(related.similarity * 100)}% similar)
            </RelatedPassageLink>
          ))}
        </RelatedPassagesSection>
      )}

      <ActionBar>
        <ActionButton onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? '🔼 Show Less' : '🔽 Show More'}
        </ActionButton>
        <ActionButton>
          📌 Bookmark
        </ActionButton>
        <ActionButton>
          📝 Add Note
        </ActionButton>
        <ActionButton>
          🔗 Share
        </ActionButton>
      </ActionBar>
    </PassageContainer>
  );
};

export default EnhancedPassageDisplay;