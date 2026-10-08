const assignments = new Map<string, readonly unknown[]>();

// Demo palettes are randomized once per application session, not per mount.
export function sessionShuffle<T>(key: string, values: readonly T[]): T[] {
  if (!assignments.has(key)) {
    const shuffled = [...values];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j]!, shuffled[i]!];
    }
    assignments.set(key, shuffled);
  }
  return [...assignments.get(key)!] as T[];
}
