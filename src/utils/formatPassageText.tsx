import React from 'react';

export function formatPassageText(text: string): React.ReactNode {
  // Split on curly single quote pairs: \u2018...\u2019
  const parts = text.split(/(\u2018[^\u2019]+\u2019)/g);
  if (parts.length === 1) return text;

  return parts.map((part, i) => {
    if (part.startsWith('\u2018') && part.endsWith('\u2019')) {
      const inner = part.slice(1, -1);
      return <em key={i}>{inner}</em>;
    }
    return part;
  });
}
