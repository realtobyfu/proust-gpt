import { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Passage } from './useStreamingQuery';
import { frenchName } from '../utils/frenchNames';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/** A passage arrived over SSE as a truncated preview and needs its full text lazy-loaded. */
export function isPassageTruncated(p: Passage): boolean {
  return p._truncated === true || (p.text?.endsWith('…') ?? false);
}

interface UsePassageTextOptions {
  /** Prefix the source label with the `[n]` citation index (PassageCard does; ReaderPanel doesn't). */
  includeCitation?: boolean;
}

/**
 * Shared passage text/translation resolution + source label (I2).
 *
 * Consolidates the ~150 lines previously duplicated between PassageCard and
 * ReaderPanel: EN/FR full-text lazy-loading, the "see original" toggle, display
 * text resolution, and the source label. Full/French text is keyed by passage
 * index so a single hook instance serves a whole carousel.
 */
export function usePassageText(passage: Passage | null, options: UsePassageTextOptions = {}) {
  const { i18n } = useTranslation();
  const isFr = i18n.language === 'fr';

  const [showOriginal, setShowOriginal] = useState(false);
  const [frenchTexts, setFrenchTexts] = useState<Record<number, string | null>>({});
  const [fetchingFr, setFetchingFr] = useState(false);
  const [fullTexts, setFullTexts] = useState<Record<number, { text: string; text_fr?: string }>>({});

  // Lazy-load full EN+FR text for a truncated passage.
  const loadFullText = useCallback(async (passageIndex: number) => {
    if (fullTexts[passageIndex] !== undefined) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/read/passage_text?index=${passageIndex}&lang=both`);
      const data = await res.json();
      if (data.text) {
        setFullTexts(prev => ({
          ...prev,
          [passageIndex]: { text: data.text, text_fr: data.text_fr || undefined },
        }));
      }
    } catch {
      // Silently fall back to the preview text.
    }
  }, [fullTexts]);

  const fetchFrenchText = useCallback(async (passageIndex: number) => {
    if (frenchTexts[passageIndex] !== undefined) return;
    setFetchingFr(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/read/passage_text?index=${passageIndex}&lang=fr`);
      const data = await res.json();
      setFrenchTexts(prev => ({
        ...prev,
        [passageIndex]: data.text_unavailable ? null : (data.text || null),
      }));
    } catch {
      setFrenchTexts(prev => ({ ...prev, [passageIndex]: null }));
    } finally {
      setFetchingFr(false);
    }
  }, [frenchTexts]);

  const toggleOriginal = useCallback(() => {
    const next = !showOriginal;
    setShowOriginal(next);
    if (next && passage && !passage.text_fr && passage.index != null) {
      fetchFrenchText(passage.index);
    }
  }, [showOriginal, passage, fetchFrenchText]);

  const full = passage && passage.index != null ? fullTexts[passage.index] : undefined;
  const enText = full?.text ?? passage?.text ?? '';
  const frText = full?.text_fr ?? passage?.text_fr
    ?? (passage && passage.index != null ? frenchTexts[passage.index] : undefined);

  let displayText = '';
  if (passage) {
    if (isFr) displayText = frText || enText;
    else if (showOriginal && frText) displayText = frText;
    else displayText = enText;
  }

  const showFrUnavailable = !!passage && showOriginal && !isFr && !frText
    && passage.index != null && frenchTexts[passage.index] === null;

  const canShowOriginalToggle = !!passage && !isFr && (!!passage.text_fr || passage.index != null);

  const sourceLabel = useMemo(() => {
    if (!passage) return '';
    const citationPrefix = options.includeCitation && passage.citation_index != null
      ? `[${passage.citation_index}] ` : '';
    const indexSuffix = passage.index != null ? `, §${passage.index}` : '';
    return citationPrefix + [
      isFr ? frenchName(passage.book || '') || 'À la recherche du temps perdu' : passage.book || 'In Search of Lost Time',
      isFr && passage.chapter ? frenchName(passage.chapter) : passage.chapter,
    ].filter(Boolean).join(' — ') + indexSuffix;
  }, [passage, isFr, options.includeCitation]);

  return {
    isFr,
    showOriginal,
    toggleOriginal,
    displayText,
    showFrUnavailable,
    fetchingFr,
    canShowOriginalToggle,
    sourceLabel,
    loadFullText,
  };
}
