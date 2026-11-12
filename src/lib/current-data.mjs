export function freshness(snapshot, now = new Date()) {
  if (!snapshot || snapshot.mode !== 'live' || typeof snapshot.fetchedAt !== 'string') return 'unavailable';
  const time = Date.parse(snapshot.fetchedAt);
  const age = now.getTime() - time;
  if (!Number.isFinite(age) || age < 0) return 'unavailable';
  return age >= 24 * 60 * 60 * 1000 ? 'stale' : 'current';
}

export function scoreText(side, scoringType) {
  if (side === null) return 'BYE';
  if (!side || side.available !== true) return 'Unavailable';
  if (scoringType === 'H2H_CATEGORY') {
    const r = side.categoryRecord;
    if (!r || ![r.wins, r.losses, r.ties].every(x => Number.isInteger(x) && x >= 0)) return 'Unavailable';
    return `${r.wins}–${r.losses}–${r.ties}`;
  }
  if (scoringType === 'H2H_POINTS' && typeof side.points === 'number' && Number.isFinite(side.points)) {
    return side.points.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }
  return 'Unavailable';
}
