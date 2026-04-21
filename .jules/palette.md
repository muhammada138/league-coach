# Palette's Journal

## 2024-03-24 - Accessible Hover-Revealed Actions
**Learning:** In the existing codebase, action groups (like save/remove buttons on lists) were implemented using Tailwind's `opacity-0 group-hover:opacity-100`. This creates an accessibility barrier for keyboard users who navigate via `Tab`, as the actions never become visible.
**Action:** When creating hover-revealed element groups, always include `focus-within:opacity-100` on the parent container, or `focus-visible:opacity-100 focus-visible:ring-2` on the interactive element itself to ensure it becomes visible and properly outlined during keyboard navigation.
