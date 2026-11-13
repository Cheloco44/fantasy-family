// Presentation only: never rewrite ESPN source names or identifiers.
export function teamLabel(teamId, cast={}) {
  if (!Number.isInteger(teamId) || teamId<1) return 'Team unavailable';
  const approved=cast[String(teamId)]?.teamName;
  return typeof approved==='string' && approved.trim() ? approved : `Team ${teamId}`;
}
