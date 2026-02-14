# Future Features

Features removed during cleanup. Notes on how to bring each back.

## Removed Components

### JourneyMap (`src/components/JourneyMap.tsx`)
Visual volume progress map showing the reader's position across all seven volumes.
**To implement:** Needs backend persistence for per-user progress. Track passage indices seen per volume, render as a horizontal bar chart or timeline.

### ProgressTracker (`src/components/ProgressTracker.tsx`)
Reading stats dashboard (passages read, time spent, volumes visited).
**To implement:** Store session stats in localStorage or backend. Aggregate from passage history and display in a sidebar or modal.

### ReadingPaths (`src/components/ReadingPaths.tsx`)
Curated reading path cards (e.g. "Memory & Time", "Love & Jealousy") using `reading_paths.json`.
**To implement:** Import `reading_paths.json`, render as clickable cards that pre-fill queries or guide the user through a sequence of prompts.

### MessageActions (`src/components/MessageActions.tsx`)
Copy/regenerate buttons for chat messages.
**To implement:** Add a floating action bar on hover over AI messages. Copy uses `navigator.clipboard.writeText()`. Regenerate re-sends the last user message.

### LoadingDots (`src/components/LoadingDots.tsx`)
Animated loading dots indicator.
**To implement:** CSS keyframe animation with three dots. Can replace the inline "Searching through Proust's work..." text.

## Removed Hooks

### useKeyboardShortcuts (`src/hooks/useKeyboardShortcuts.ts`)
Keyboard shortcut registration hook.
**To implement:** Register global keydown listeners. Useful shortcuts: `/` to focus input, `Esc` to close sidebar, `Ctrl+B` for bookmarks.

## Removed Sidebar Items

### Timeline
Chronological timeline of events in the novel.
**To implement:** Extract temporal data from `parsed.json` metadata. Render as a vertical timeline component with clickable events.

### Places
Map or list of locations in the novel (Combray, Balbec, Paris, etc.).
**To implement:** Extract location data from `parsed.json`. Could use a simple illustrated map or a categorized list linking to relevant passages.

## Not Yet Ported

### Backend Session Tracking (`server_enhanced.py`)
Session-based progress tracking, reading history, and context-aware retrieval.
**To implement:** Port session endpoints from `server_enhanced.py` into `server.py`. Add `/api/session` endpoints for saving/loading user progress.
