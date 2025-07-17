import React, { useState } from 'react';
import styled from 'styled-components';

const PassageContainer = styled.div`
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

interface PassageProps {
  text: string;
  volume?: string;
  page?: number;
  narrativeContext?: string;
  characters?: string[];
  onBookmark?: () => void;
}

const PassageDisplay: React.FC<PassageProps> = ({
  text,
  volume = "In Search of Lost Time",
  page,
  narrativeContext,
  characters = [],
  onBookmark
}) => {
  const [showContext, setShowContext] = useState(false);

  return (
    <PassageContainer>
      {(volume || page) && (
        <PassageMetadata>
          {volume && `From ${volume}`}
          {volume && page && ', '}
          {page && `p. ${page}`}
        </PassageMetadata>
      )}
      
      <PassageText>{text}</PassageText>
      
      <ActionLinks>
        <ContextLink onClick={() => setShowContext(!showContext)}>
          {showContext ? 'Hide context' : 'See context'}
        </ContextLink>
        {onBookmark && (
          <ContextLink onClick={onBookmark}>
            Mark this passage
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
    </PassageContainer>
  );
};

export default PassageDisplay;