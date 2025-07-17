import React from 'react';
import styled from 'styled-components';
import { theme } from '../styles/theme';

const PathsContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
`;

const PathCard = styled.div`
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid ${theme.colors.border};
  border-radius: 16px;
  padding: 2rem;
  cursor: pointer;
  transition: all ${theme.transitions.default};
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: ${props => props.color || theme.colors.primary};
    transform: scaleX(0);
    transition: transform ${theme.transitions.default};
    transform-origin: left;
  }
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    
    &::before {
      transform: scaleX(1);
    }
  }
`;

const PathIcon = styled.div`
  width: 48px;
  height: 48px;
  background: ${props => props.color || theme.colors.primary};
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
  font-size: 1.5rem;
  color: white;
`;

const PathTitle = styled.h3`
  font-family: ${theme.fonts.heading};
  font-size: 1.3rem;
  margin-bottom: 0.5rem;
  color: ${theme.colors.text};
`;

const PathDuration = styled.span`
  font-size: 0.9rem;
  color: ${theme.colors.textLight};
  display: block;
  margin-bottom: 1rem;
`;

const PathDescription = styled.p`
  font-size: 1rem;
  line-height: 1.5;
  color: ${theme.colors.textLight};
  margin-bottom: 1.5rem;
`;

const PathProgress = styled.div`
  background: rgba(0, 0, 0, 0.05);
  height: 4px;
  border-radius: 2px;
  overflow: hidden;
  margin-top: auto;
`;

const ProgressBar = styled.div`
  height: 100%;
  background: ${props => props.color || theme.colors.primary};
  width: ${props => props.progress || 0}%;
  transition: width ${theme.transitions.slow};
`;

export interface ReadingPath {
  id: string;
  title: string;
  duration: string;
  description: string;
  icon: string;
  color: string;
  progress?: number;
  route: string;
}

interface ReadingPathsProps {
  paths: ReadingPath[];
  onSelectPath: (path: ReadingPath) => void;
}

const ReadingPaths: React.FC<ReadingPathsProps> = ({ paths, onSelectPath }) => {
  return (
    <PathsContainer>
      {paths.map(path => (
        <PathCard
          key={path.id}
          color={path.color}
          onClick={() => onSelectPath(path)}
        >
          <PathIcon color={path.color}>
            {path.icon}
          </PathIcon>
          <PathTitle>{path.title}</PathTitle>
          <PathDuration>{path.duration}</PathDuration>
          <PathDescription>{path.description}</PathDescription>
          {path.progress !== undefined && (
            <PathProgress>
              <ProgressBar color={path.color} progress={path.progress} />
            </PathProgress>
          )}
        </PathCard>
      ))}
    </PathsContainer>
  );
};

export default ReadingPaths;