## 2024-04-18 - [Memoizing Expensive Local State Manipulations]
**Learning:** Found an anti-pattern in `SearchInput.jsx` where search suggestions filtering/deduplication across historical/saved searches ran synchronously on every render using an IIFE. This is highly inefficient in a React environment as inputs naturally re-render frequently (e.g. typing, or layout shifts).
**Action:** Always verify if complex data manipulations (especially mapping/filtering sets of data) inside components are memoized (`useMemo`) or pulled out of the render loop entirely, rather than just executing inline.
