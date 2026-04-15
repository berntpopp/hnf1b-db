# feat(api): implement incremental variant loading with cursor pagination

## Summary
Replace hardcoded 1000 variant limit with proper cursor pagination and incremental loading. Current implementation breaks when database exceeds limit.

**Current:** Hard limit of 1000 variants for priority sorting and visualizations
**Target:** Scalable pagination with progressive loading for unlimited variants

## Acceptance Criteria

### Backend
- [ ] Add `GET /variants/count` endpoint for total variant monitoring
- [ ] Implement cursor-based pagination in variant endpoints
- [ ] Add server-side priority sorting by classification
- [ ] Return `total_count` and `next_cursor` in responses
- [ ] Optimize queries with proper indexes

### Frontend
- [ ] Remove `MAX_VARIANTS_FOR_PRIORITY_SORT` limitation
- [ ] Implement incremental data fetching with loading states
- [ ] Add "Load More" button for variant table
- [ ] Update visualizations to handle streaming data
- [ ] Add progress indicator (e.g., "Loaded 250 / 1,200 variants")
- [ ] Cache loaded data to prevent redundant fetches
- [ ] Add total variant count display in UI

### Performance
- [ ] Benchmark: Load 1,000 variants in <2s
- [ ] Ensure smooth scrolling with virtualization
- [ ] Memory usage remains stable during incremental loads

## Dependencies
- Related to #62 (JSON:API pagination spec)

## Priority
**P1 (High)** - Prevents future data loss and system failure

## Labels
`enhancement`, `frontend`, `backend`, `api`, `performance`, `p1-high`
