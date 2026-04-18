## 2024-05-18 - [Security] Prevent XSS via dangerouslySetInnerHTML
**Vulnerability:** Use of `dangerouslySetInnerHTML` to inject static styles into React components (e.g. RegionSelector.jsx) acts as a potential XSS vector and violates React security best practices.
**Learning:** Static styles can be safely extracted to the global stylesheet (e.g., `index.css`). Be careful to uniquely name any migrated `@keyframes` and utility classes to avoid naming collisions with existing styles.
**Prevention:** Avoid `dangerouslySetInnerHTML`. Always use standard CSS files or framework styling features (like Tailwind utility classes) for static CSS definitions.
