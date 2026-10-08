const assignments = new Map<string, readonly unknown[]>();

// A stable demo permutation preserves the same decorations across cold starts.
export function sessionShuffle<T>(key: string, values: readonly T[]): T[] {
  if (!assignments.has(key)) {
    const shuffled = [...values];
    let seed = 2166136261;
    for (const char of key) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619);
    const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j]!, shuffled[i]!];
    }
    assignments.set(key, shuffled);
  }
  return [...assignments.get(key)!] as T[];
}
