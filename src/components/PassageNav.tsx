import React from 'react';
import styled from 'styled-components';
import { useTranslation } from 'react-i18next';

const NavFooter = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
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

interface PassageNavProps {
  count: number;
  currentIndex: number;
  onNavigate: (index: number, direction: 'left' | 'right') => void;
  /** Stop click propagation (PassageCard's carousel lives inside a clickable card). */
  stopClickPropagation?: boolean;
}

/** Shared prev/next arrows + dot indicators for passage carousels (I2). */
const PassageNav: React.FC<PassageNavProps> = ({ count, currentIndex, onNavigate, stopClickPropagation }) => {
  const { t } = useTranslation();
  if (count <= 1) return null;

  const stop = (e: React.MouseEvent) => {
    if (stopClickPropagation) e.stopPropagation();
  };

  return (
    <NavFooter onClick={stop}>
      <NavArrow
        onClick={(e) => { stop(e); if (currentIndex > 0) onNavigate(currentIndex - 1, 'right'); }}
        disabled={currentIndex === 0}
        aria-label={t('passage.previousPassage')}
      >
        &#8249;
      </NavArrow>
      {Array.from({ length: count }).map((_, i) => (
        <Dot
          key={i}
          $active={i === currentIndex}
          onClick={(e) => { stop(e); onNavigate(i, i > currentIndex ? 'left' : 'right'); }}
          aria-label={t('passage.goToPassage', { number: i + 1 })}
        />
      ))}
      <NavArrow
        onClick={(e) => { stop(e); if (currentIndex < count - 1) onNavigate(currentIndex + 1, 'left'); }}
        disabled={currentIndex === count - 1}
        aria-label={t('passage.nextPassage')}
      >
        &#8250;
      </NavArrow>
    </NavFooter>
  );
};

export default PassageNav;
