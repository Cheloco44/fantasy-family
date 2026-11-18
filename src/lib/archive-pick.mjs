// Curation is separate from the recap catalog: new daily artwork is never auto-enrolled.
export function buildArchivePool(curated, memes) {
  const seen = new Set();
  return curated.flatMap(entry => {
    const meme = memes.find(m => m.id === entry.memeId);
    if (!meme || seen.has(meme.id) || meme.approvalStatus !== 'approved'
        || meme.contextType !== 'evergreen' || meme.scoreContext
        || typeof meme.image !== 'string'
        || !/^memes\/approved\/[a-zA-Z0-9_-]+\.(webp|png|jpg)$/.test(meme.image)
        || !['title', 'description', 'joke'].every(key => typeof entry[key] === 'string' && entry[key].trim())) return [];
    seen.add(meme.id);
    return [{ ...meme, title: entry.title, description: entry.description, joke: entry.joke }];
  });
}

// A stable shuffled deck: one shared pick per Arizona date, no repeats within a deck.
// No network, storage, API keys, or build-time scheduler is needed for rollover.
export function pickArchive(items, now = new Date()) {
  if (!(now instanceof Date) || Number.isNaN(now.getTime())) throw new TypeError('Invalid archive clock');
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Phoenix', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const value = type => parts.find(part => part.type === type).value;
  const date = `${value('year')}-${value('month')}-${value('day')}`;
  const day = Math.floor(Date.parse(`${date}T00:00:00Z`) / 86400000);
  const hash = id => {
    let result = 2166136261;
    for (const char of id) result = Math.imul(result ^ char.charCodeAt(0), 16777619) >>> 0;
    return result;
  };
  if (items.some(item => typeof item.id !== 'string' || !item.id)
      || new Set(items.map(item => item.id)).size !== items.length) {
    throw new TypeError('Archive IDs must be unique nonempty strings');
  }
  const deck = [...items].sort((a, b) => hash(a.id) - hash(b.id) || a.id.localeCompare(b.id));
  const index = deck.length ? ((day % deck.length) + deck.length) % deck.length : -1;
  return { date, item: deck[index] ?? null };
}
