import { useEffect } from 'react';

interface ShortcutHandler {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  callback: () => void;
}

function useKeyboardShortcuts(shortcuts: ShortcutHandler[]) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      shortcuts.forEach(({ key, ctrlKey, metaKey, shiftKey, callback }) => {
        const isCtrlPressed = ctrlKey ? event.ctrlKey : true;
        const isMetaPressed = metaKey ? event.metaKey : true;
        const isShiftPressed = shiftKey ? event.shiftKey : true;

        if (
          event.key.toLowerCase() === key.toLowerCase() &&
          isCtrlPressed &&
          isMetaPressed &&
          isShiftPressed
        ) {
          event.preventDefault();
          callback();
        }
      });
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [shortcuts]);
}

export default useKeyboardShortcuts;