import type { Digest } from './types';
import digestData from '../../data/daily/latest.json';

const fallback: Digest = {
  schemaVersion: 1,
  date: new Date().toISOString().slice(0, 10),
  generatedAt: new Date().toISOString(),
  mode: 'empty',
  stats: { discovered: 0, afterDeduplication: 0, deepReviewed: 0, recommended: 0 },
  articles: [],
  errors: [],
};

export function getLatestDigest(): Digest {
  try {
    return digestData as unknown as Digest;
  } catch {
    return fallback;
  }
}

export function formatDigestDate(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(date);
}

export function formatPublishedAt(value: string): string {
  if (!value) return '时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
