# fix(frontend): variant search functionality not working

## Summary
Variant search UI is present but search functionality is broken or incomplete. Users cannot filter variants by text search queries.

**Current:** Search input exists but queries don't filter results
**Target:** Working text search with HGVS, coordinates, and ID support

## Acceptance Criteria
- [ ] Identify root cause (API endpoint, frontend logic, or both)
- [ ] Fix search query parameter passing to backend
- [ ] Implement debounced search (300ms delay)
- [ ] Add loading state during search
- [ ] Handle empty results gracefully
- [ ] Add error handling for malformed queries
- [ ] Verify search works for: HGVS, coordinates, variant IDs
- [ ] Add search result count display

## Priority
**P1 (High)** - Core user functionality

## Labels
`bug`, `frontend`, `p1-high`, `user-experience`
