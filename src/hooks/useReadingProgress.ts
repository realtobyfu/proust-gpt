import { useLocalStorage } from './useLocalStorage';

export interface ReadingPosition {
  volume: number;
  chapter: string;
  passageIndex: number;
  page: number;
  timestamp: string;
}

export interface ReadingProgressData {
  lastPosition: ReadingPosition | null;
  readPassages: number[];
}

const STORAGE_KEY = 'proust-reading-progress';

export function useReadingProgress() {
  const [progress, setProgress] = useLocalStorage<ReadingProgressData>(STORAGE_KEY, {
    lastPosition: null,
    readPassages: [],
  });

  const setLastPosition = (volume: number, chapter: string, passageIndex: number, page: number = 0) => {
    setProgress(prev => ({
      ...prev,
      lastPosition: {
        volume,
        chapter,
        passageIndex,
        page,
        timestamp: new Date().toISOString(),
      },
    }));
  };

  const markPassageRead = (passageIndex: number) => {
    setProgress(prev => {
      if (prev.readPassages.includes(passageIndex)) return prev;
      return {
        ...prev,
        readPassages: [...prev.readPassages, passageIndex],
      };
    });
  };

  /** Atomically update position + batch-mark passages read in one state write */
  const setPageProgress = (volume: number, chapter: string, passageIndex: number, page: number, passageIndices: number[]) => {
    setProgress(prev => {
      const newIndices = passageIndices.filter(i => !prev.readPassages.includes(i));
      return {
        ...prev,
        lastPosition: {
          volume,
          chapter,
          passageIndex,
          page,
          timestamp: new Date().toISOString(),
        },
        readPassages: newIndices.length > 0
          ? [...prev.readPassages, ...newIndices]
          : prev.readPassages,
      };
    });
  };

  const getChapterProgress = (firstIndex: number, lastIndex: number): number => {
    if (lastIndex <= firstIndex) return 0;
    const chapterRange = lastIndex - firstIndex + 1;
    const readInChapter = progress.readPassages.filter(
      i => i >= firstIndex && i <= lastIndex
    ).length;
    return Math.round((readInChapter / chapterRange) * 100);
  };

  return {
    lastPosition: progress.lastPosition,
    readPassages: progress.readPassages,
    setLastPosition,
    markPassageRead,
    setPageProgress,
    getChapterProgress,
  };
}

export default useReadingProgress;
