export type Category = 'ai-news' | 'product-insight' | 'career' | 'other';
export type ReadingTier = 'must-read' | 'worth-reading' | 'signal' | 'unselected';

export interface ImportantTerm {
  term: string;
  explanationZh: string;
}

export interface Article {
  id: string;
  title: string;
  titleZh: string;
  url: string;
  author: string;
  source: string;
  publishedAt: string;
  discoveredAt: string;
  language: string;
  category: Category;
  summaryZh: string;
  translationZh?: string;
  translationStatus?: 'available' | 'pending' | 'not-needed';
  sourceSnippet?: string;
  keyIdeas: string[];
  counterPoint: string;
  whyForMe: string;
  topics: string[];
  importantTerms: ImportantTerm[];
  scores: Record<string, number>;
  finalScore: number;
  preRankingScore?: number;
  readingTier: ReadingTier;
  socialSignals: Record<string, string | number>;
  contentAvailability: 'full' | 'partial';
  estimatedReadingMinutes: number | null;
  duplicateSources?: string[];
}

export interface Digest {
  schemaVersion: number;
  date: string;
  generatedAt: string;
  mode: string;
  stats: {
    discovered: number;
    afterDeduplication: number;
    deepReviewed: number;
    recommended: number;
  };
  articles: Article[];
  errors: Array<{ source: string; error: string; timestamp: string }>;
}
