import React, { useState } from 'react';
import styled from 'styled-components';
import { useReadingProgress } from '../hooks/useReadingProgress';

const Container = styled.div`
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
`;

const VolumeCard = styled.div`
  margin-bottom: 1.5rem;
`;

const VolumeHeader = styled.button`
  width: 100%;
  background: none;
  border: none;
  padding: 1rem 0;
  cursor: pointer;
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #e0d8cf;
  transition: border-color 0.2s ease;

  &:hover {
    border-bottom-color: #8b4513;
  }
`;

const VolumeNumber = styled.span`
  font-family: 'Belgrano', serif;
  font-size: 0.85rem;
  color: #8b4513;
  white-space: nowrap;
`;

const VolumeTitle = styled.span`
  font-family: 'Belgrano', serif;
  font-size: 1.25rem;
  color: #333;
  flex: 1;
`;

const Arrow = styled.span<{ $open: boolean }>`
  font-size: 0.7rem;
  color: #999;
  transition: transform 0.2s ease;
  transform: rotate(${props => props.$open ? '90deg' : '0deg'});
`;

const ChapterList = styled.div<{ $open: boolean }>`
  max-height: ${props => props.$open ? '1000px' : '0'};
  overflow: hidden;
  transition: max-height 0.3s ease;
`;

const ChapterRow = styled.button`
  width: 100%;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid #eee;
  border-radius: 6px;
  padding: 0.9rem 1rem;
  margin: 0.35rem 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  transition: all 0.15s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.9);
    border-color: #d4ccc3;
    transform: translateX(4px);
  }
`;

const ChapterName = styled.span`
  font-family: 'Georgia', serif;
  font-size: 1rem;
  color: #333;
`;

const ChapterMeta = styled.span`
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 0.78rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 0.75rem;
`;

const ProgressBar = styled.div`
  width: 48px;
  height: 3px;
  background: #e0d8cf;
  border-radius: 2px;
  overflow: hidden;
`;

const ProgressFill = styled.div<{ $percent: number }>`
  height: 100%;
  width: ${props => props.$percent}%;
  background: #8b4513;
  transition: width 0.3s ease;
`;

interface Volume {
  volume: number;
  volume_name: string;
  chapter_count: number;
  total_passages: number;
  chapters: {
    name: string;
    passage_count: number;
    first_index: number;
    last_index: number;
  }[];
}

interface TableOfContentsProps {
  volumes: Volume[];
  onSelectChapter: (volume: number, chapter: string) => void;
}

const TableOfContents: React.FC<TableOfContentsProps> = ({ volumes, onSelectChapter }) => {
  const [openVolumes, setOpenVolumes] = useState<Set<number>>(() => new Set([1]));
  const { getChapterProgress } = useReadingProgress();

  const toggleVolume = (vol: number) => {
    setOpenVolumes(prev => {
      const next = new Set(prev);
      if (next.has(vol)) next.delete(vol);
      else next.add(vol);
      return next;
    });
  };

  return (
    <Container>
      {volumes.map(vol => {
        const isOpen = openVolumes.has(vol.volume);
        return (
          <VolumeCard key={vol.volume}>
            <VolumeHeader onClick={() => toggleVolume(vol.volume)}>
              <Arrow $open={isOpen}>&#9654;</Arrow>
              <VolumeNumber>Vol. {vol.volume}</VolumeNumber>
              <VolumeTitle>{vol.volume_name}</VolumeTitle>
            </VolumeHeader>

            <ChapterList $open={isOpen}>
              {vol.chapters.map(ch => {
                const progress = getChapterProgress(ch.first_index, ch.last_index);
                return (
                  <ChapterRow
                    key={ch.name}
                    onClick={() => onSelectChapter(vol.volume, ch.name)}
                  >
                    <ChapterName>{ch.name}</ChapterName>
                    <ChapterMeta>
                      {progress > 0 && (
                        <ProgressBar>
                          <ProgressFill $percent={progress} />
                        </ProgressBar>
                      )}
                    </ChapterMeta>
                  </ChapterRow>
                );
              })}
            </ChapterList>
          </VolumeCard>
        );
      })}
    </Container>
  );
};

export default TableOfContents;
