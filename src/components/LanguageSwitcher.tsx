import React from 'react';
import styled from 'styled-components';
import { useLanguage } from '../contexts/LanguageContext';

const Wrapper = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
`;

const Option = styled.button<{ $active: boolean }>`
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: inherit;
  font-size: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
  font-weight: ${props => props.$active ? 600 : 400};
  color: ${props => props.$active ? '#333' : '#aaa'};
  transition: color 0.15s ease;

  &:hover {
    color: ${props => props.$active ? '#333' : '#666'};
  }
`;

const Separator = styled.span`
  color: #ccc;
  font-weight: 300;
  user-select: none;
`;

const LanguageSwitcher: React.FC = () => {
  const { language, setLanguage } = useLanguage();

  return (
    <Wrapper>
      <Option $active={language === 'fr'} onClick={() => setLanguage('fr')}>
        FR
      </Option>
      <Separator>|</Separator>
      <Option $active={language === 'en'} onClick={() => setLanguage('en')}>
        EN
      </Option>
    </Wrapper>
  );
};

export default LanguageSwitcher;
