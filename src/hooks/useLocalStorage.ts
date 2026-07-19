import { useState, useEffect, useCallback } from 'react';

// Fired same-tab so independent consumers of the same key stay in sync
// (the native `storage` event only fires in *other* tabs).
const LOCAL_STORAGE_EVENT = 'proust-local-storage';

export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((prev: T) => T)) => void] {
  // Read + parse the current value from localStorage (or the initial value).
  const readValue = useCallback((): T => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
    // initialValue is intentionally excluded — callers pass a fresh literal each
    // render, which would otherwise make this callback (and the sync effect)
    // change identity on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const [storedValue, setStoredValue] = useState<T>(readValue);

  const setValue = useCallback((value: T | ((prev: T) => T)) => {
    if (typeof window === 'undefined') {
      console.warn(`Tried setting localStorage key "${key}" outside of a client`);
      return;
    }
    try {
      // Read the freshest persisted value rather than a captured `storedValue`,
      // so functional updates from stale closures and writes from other
      // consumers of the same key don't clobber each other (I5).
      let current: T;
      try {
        const item = window.localStorage.getItem(key);
        current = item ? JSON.parse(item) : initialValue;
      } catch {
        current = initialValue;
      }
      const newValue = value instanceof Function ? value(current) : value;
      window.localStorage.setItem(key, JSON.stringify(newValue));
      setStoredValue(newValue);
      // Notify other hook instances in this tab.
      window.dispatchEvent(new CustomEvent(LOCAL_STORAGE_EVENT, { detail: { key } }));
    } catch (error) {
      console.warn(`Error setting localStorage key "${key}":`, error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Sync when another consumer (same tab) or another tab changes this key.
  useEffect(() => {
    setStoredValue(readValue());
    const handleChange = (e: Event) => {
      if (e instanceof StorageEvent) {
        if (e.key !== null && e.key !== key) return;
      } else if (e instanceof CustomEvent && e.detail?.key && e.detail.key !== key) {
        return;
      }
      setStoredValue(readValue());
    };
    window.addEventListener('storage', handleChange);
    window.addEventListener(LOCAL_STORAGE_EVENT, handleChange);
    return () => {
      window.removeEventListener('storage', handleChange);
      window.removeEventListener(LOCAL_STORAGE_EVENT, handleChange);
    };
  }, [key, readValue]);

  return [storedValue, setValue];
}

export default useLocalStorage;
