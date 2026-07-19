import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import { useTranslation } from 'react-i18next';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

interface SearchCriteria {
  keywords?: string[];
  volume?: number;
  themes?: string[];
}

interface PathModule {
  day?: number;
  title: string;
  description?: string;
  context?: string;
  search_criteria?: SearchCriteria;
}

export interface ReadingPath {
  id: string;
  title: string;
  description: string;
  duration?: string;
  difficulty?: string;
  modules: PathModule[];
}

interface ReadingPathsProps {
  onClose: () => void;
  /** Called with a constructed Explore prompt when a module is chosen. */
  onSelectModule: (prompt: string) => void;
}

const Backdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(42, 32, 22, 0.35);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 3rem 1rem;
  overflow-y: auto;
  z-index: 500;
`;

const Panel = styled.div`
  background: #faf8f5;
  border: 1px solid #e0d8cf;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  width: 100%;
  max-width: 640px;
  padding: 2rem 2rem 2.5rem;
  position: relative;
`;

const CloseButton = styled.button`
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: none;
  color: #8b4513;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: rgba(139, 69, 19, 0.08);
  }
`;

const Title = styled.h2`
  font-family: 'Belgrano', serif;
  font-weight: 400;
  font-size: 1.6rem;
  color: #2a2a2a;
  margin: 0 0 0.4rem;
`;

const Intro = styled.p`
  font-family: 'Georgia', serif;
  font-size: 0.95rem;
  color: #6e6459;
  line-height: 1.6;
  margin: 0 0 1.5rem;
`;

const PathCard = styled.div`
  border: 1px solid #e0d8cf;
  border-radius: 10px;
  background: #fff;
  margin-bottom: 0.9rem;
  overflow: hidden;
`;

const PathHeader = styled.button<{ $open: boolean }>`
  width: 100%;
  text-align: left;
  background: ${props => props.$open ? 'rgba(139, 69, 19, 0.05)' : 'none'};
  border: none;
  padding: 1rem 1.25rem;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.05);
  }
`;

const PathTitle = styled.span`
  font-family: 'Belgrano', serif;
  font-size: 1.1rem;
  color: #8b4513;
`;

const PathMeta = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.75rem;
  color: #8a8178;
`;

const PathDesc = styled.span`
  font-family: 'Georgia', serif;
  font-size: 0.88rem;
  color: #5f5648;
  line-height: 1.5;
`;

const ModuleList = styled.div`
  border-top: 1px solid #eee;
  padding: 0.5rem 0.75rem 0.75rem;
`;

const ModuleItem = styled.button`
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
  cursor: pointer;
  display: block;
  transition: background 0.12s ease;

  &:hover {
    background: rgba(139, 69, 19, 0.06);
  }
`;

const ModuleTitle = styled.div`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.9rem;
  color: #3a3028;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.4rem;
`;

const ModuleDay = styled.span`
  font-size: 0.68rem;
  color: #8b4513;
  background: rgba(139, 69, 19, 0.08);
  border-radius: 4px;
  padding: 0.05rem 0.35rem;
  font-weight: 500;
`;

const ModuleDesc = styled.div`
  font-family: 'Georgia', serif;
  font-size: 0.82rem;
  color: #6e6459;
  line-height: 1.5;
  margin-top: 0.15rem;
`;

const ModuleCta = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.72rem;
  color: #8b4513;
  &::after { content: ' →'; }
`;

const StateNote = styled.p`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.85rem;
  color: #8a8178;
  text-align: center;
  padding: 1.5rem 0;
`;

function buildPrompt(m: PathModule): string {
  const kw = m.search_criteria?.keywords?.filter(Boolean).join(', ');
  return `Show me the passage about ${m.title}${kw ? ` (${kw})` : ''}.`;
}

const ReadingPaths: React.FC<ReadingPathsProps> = ({ onClose, onSelectModule }) => {
  const { t } = useTranslation();
  const [paths, setPaths] = useState<ReadingPath[] | null>(null);
  const [error, setError] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/read/paths`)
      .then(res => res.json())
      .then(data => {
        if (cancelled) return;
        const list = data?.paths ? (Object.values(data.paths) as ReadingPath[]) : [];
        const withModules = list.filter(p => Array.isArray(p.modules) && p.modules.length > 0);
        setPaths(withModules);
        if (withModules.length > 0) setOpenId(withModules[0].id);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => { cancelled = true; };
  }, []);

  // Close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <Backdrop onClick={onClose}>
      <Panel
        role="dialog"
        aria-modal="true"
        aria-label={t('landing.guidedPathsTitle')}
        onClick={(e) => e.stopPropagation()}
      >
        <CloseButton onClick={onClose} aria-label={t('common.close')}>&times;</CloseButton>
        <Title>{t('landing.guidedPathsTitle')}</Title>
        <Intro>{t('landing.guidedPathsIntro')}</Intro>

        {error && <StateNote>{t('landing.pathsLoadError')}</StateNote>}
        {!error && paths === null && <StateNote>{t('common.loading')}</StateNote>}
        {!error && paths !== null && paths.length === 0 && (
          <StateNote>{t('landing.pathsEmpty')}</StateNote>
        )}

        {paths?.map(path => {
          const open = openId === path.id;
          return (
            <PathCard key={path.id}>
              <PathHeader
                $open={open}
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : path.id)}
              >
                <PathTitle>{path.title}</PathTitle>
                <PathMeta>
                  {[path.duration, path.difficulty, t('landing.pathStepsLabel', { count: path.modules.length })]
                    .filter(Boolean)
                    .join(' · ')}
                </PathMeta>
                <PathDesc>{path.description}</PathDesc>
              </PathHeader>
              {open && (
                <ModuleList>
                  {path.modules.map((m, i) => (
                    <ModuleItem
                      key={`${path.id}-${i}`}
                      onClick={() => onSelectModule(buildPrompt(m))}
                    >
                      <ModuleTitle>
                        {m.day != null && <ModuleDay>{`#${m.day}`}</ModuleDay>}
                        {m.title}
                      </ModuleTitle>
                      {m.description && <ModuleDesc>{m.description}</ModuleDesc>}
                      <ModuleCta>{t('landing.pathStartStep')}</ModuleCta>
                    </ModuleItem>
                  ))}
                </ModuleList>
              )}
            </PathCard>
          );
        })}
      </Panel>
    </Backdrop>
  );
};

export default ReadingPaths;
