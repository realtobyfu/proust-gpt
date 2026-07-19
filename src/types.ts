// Shared cross-surface types.

/**
 * A saved passage. Consolidated from previously-duplicated declarations in
 * ChatPage, ReadPage, ReadingView and BookmarkDropdown (finding I4).
 */
export interface Bookmark {
  id: string;
  text: string;
  book: string;
  chapter: string;
  index?: number;
  savedAt: string;
}

/**
 * Identity match for bookmarks (I4).
 *
 * Passages arrive over SSE as truncated 200-char previews and the full text is
 * lazy-loaded later, so matching purely on text breaks the star state. Prefer
 * the stable corpus `index`; fall back to text equality for legacy bookmarks
 * saved before an index was recorded.
 */
export function bookmarkMatches(
  b: Pick<Bookmark, 'index' | 'text'>,
  passage: { index?: number | null; text?: string },
): boolean {
  if (b.index != null && passage.index != null) {
    return b.index === passage.index;
  }
  return !!passage.text && b.text === passage.text;
}
