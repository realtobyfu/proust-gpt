import React, { createContext, useContext, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

interface LanguageContextType {
  language: string;
  setLanguage: (lang: string) => void;
  textLanguage: string;
  setTextLanguage: (lang: string) => void;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => {},
  textLanguage: 'en',
  setTextLanguage: () => {},
});

export const useLanguage = () => useContext(LanguageContext);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { i18n } = useTranslation();
  const [language, setLanguageState] = useState(i18n.language || 'en');
  const [textLanguage, setTextLanguageState] = useState(
    () => localStorage.getItem('proust-text-language') || 'en'
  );

  const setLanguage = (lang: string) => {
    setLanguageState(lang);
    i18n.changeLanguage(lang);
    setTextLanguage(lang);
  };

  const setTextLanguage = (lang: string) => {
    setTextLanguageState(lang);
    localStorage.setItem('proust-text-language', lang);
  };

  useEffect(() => {
    const handleLanguageChange = (lng: string) => {
      setLanguageState(lng);
    };
    i18n.on('languageChanged', handleLanguageChange);
    return () => {
      i18n.off('languageChanged', handleLanguageChange);
    };
  }, [i18n]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, textLanguage, setTextLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
};
