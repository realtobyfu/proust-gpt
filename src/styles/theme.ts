export const theme = {
  colors: {
    primary: '#8b4513',
    secondary: '#f7f4f0',
    background: '#f7f4f0',
    text: '#333',
    textLight: '#555',
    white: '#fff',
    border: '#ccc',
    shadow: 'rgba(0, 0, 0, 0.1)',
    messageBg: 'rgba(255, 255, 255, 0.6)',
    userMessageBg: 'rgba(139, 69, 19, 0.1)',
    proustMessageBg: 'rgba(255, 255, 255, 0.8)',
    reflectAccent: '#5a6b5a',
  },
  fonts: {
    primary: "'Georgia', serif",
    secondary: "'IBM Plex Sans', sans-serif",
    heading: "'Belgrano', serif",
  },
  breakpoints: {
    mobile: '768px',
    tablet: '1024px',
  },
  transitions: {
    default: '0.3s ease',
    slow: '0.5s ease',
  },
};

export type Theme = typeof theme;