export function yesterdayArizona(now = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Phoenix', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now).filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
  // Subtract a calendar day from the Arizona date, not from the input instant.
  const previous = new Date(Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day) - 1));
  return previous.toISOString().slice(0, 10);
}
