## 2025-02-20 - Keyboard Accessibility for Hover-Revealed Actions
**Learning:** When using Tailwind's `opacity-0 group-hover:opacity-100` pattern to hide action buttons until hover, keyboard users cannot tab to or see these buttons.
**Action:** Always include `focus-within:opacity-100` on the parent container (or `focus-visible:opacity-100` on the element itself) along with `focus-visible:ring-2` to ensure keyboard navigability.
