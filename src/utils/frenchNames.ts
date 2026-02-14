/**
 * French translations for English volume and chapter names.
 * Mirrors backend/corpus.py _FRENCH_NAMES.
 */
const FRENCH_NAMES: Record<string, string> = {
  // Volume names (both straight and curly apostrophe variants)
  "Swann's Way": "Du côté de chez Swann",
  "Swann\u2019s Way": "Du côté de chez Swann",
  "Within a Budding Grove": "À l\u2019ombre des jeunes filles en fleurs",
  "The Guermantes Way": "Le Côté de Guermantes",
  "Sodom and Gomorrah": "Sodome et Gomorrhe",
  "Cities of the Plain": "Sodome et Gomorrhe",
  "The Captive": "La Prisonnière",
  "The Fugitive": "Albertine disparue",
  "The Sweet Cheat Gone": "Albertine disparue",
  "Time Regained": "Le Temps retrouvé",
  // Chapter names (Vol 1)
  "Overture": "Combray",
  "Swann in Love": "Un amour de Swann",
  "Place-Names: The Name": "Noms de pays : le nom",
  // Chapter names (Vol 2)
  "Madame Swann at Home": "Autour de Mme Swann",
  "Place-Names: The Place": "Noms de pays : le pays",
  "Seascape, with Frieze of Girls": "Autour de Mme Swann (suite)",
  // Generic chapter names
  "Chapter 1": "Chapitre 1",
  "Chapter 2": "Chapitre 2",
  "Chapter 3": "Chapitre 3",
  "Chapter 4": "Chapitre 4",
  "Introduction": "Introduction",
};

/**
 * Translate an English volume/chapter name to French.
 * Returns the original string if no translation exists.
 */
export function frenchName(enName: string): string {
  // Try direct lookup, then normalize curly apostrophes to straight
  return FRENCH_NAMES[enName] ?? FRENCH_NAMES[enName.replace(/\u2019/g, "'")] ?? enName;
}
