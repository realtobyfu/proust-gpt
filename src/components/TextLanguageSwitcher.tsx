import React from 'react';
import styled from 'styled-components';
import { useLanguage } from '../contexts/LanguageContext';

const Pill = styled.div`
  display: inline-flex;
  align-items: center;
  background: rgba(139, 69, 19, 0.04);
  border: 1px solid #d4ccc3;
  border-radius: 12px;
  overflow: hidden;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.7rem;
`;

const Option = styled.button<{ $active: boolean }>`
  background: ${props => props.$active ? 'rgba(139, 69, 19, 0.12)' : 'transparent'};
  color: ${props => props.$active ? '#8b4513' : '#999'};
  border: none;
  padding: 0.2rem 0.45rem;
  cursor: pointer;
  font-family: inherit;
  font-size: inherit;
  font-weight: ${props => props.$active ? 600 : 400};
  transition: all 0.15s ease;

  &:hover {
    color: #8b4513;
  }
`;

const TextLanguageSwitcher: React.FC = () => {
  const { textLanguage, setTextLanguage } = useLanguage();

  return (
    <Pill>
      <Option $active={textLanguage === 'en'} onClick={() => setTextLanguage('en')}>
        EN
      </Option>
      <Option $active={textLanguage === 'fr'} onClick={() => setTextLanguage('fr')}>
        FR
      </Option>
    </Pill>
  );
};

export default TextLanguageSwitcher;
