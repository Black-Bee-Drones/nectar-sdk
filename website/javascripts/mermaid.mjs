// Zensical renders Mermaid natively (client-side, theme-aware). This module overrides
// the runtime only to make the ELK layout engine available and to keep initialization
// consistent, following the pattern documented at
// https://zensical.org/docs/authoring/diagrams/#customization
//
// ELK is registered but NOT forced globally: only diagrams that opt in via frontmatter
// (`config: { layout: elk }`) use it. This keeps class/sequence/ER diagrams on their
// native layouts, which do not support layout selection. No theme is set here on purpose
// so Zensical keeps adapting fonts/colors to the active light/dark scheme.
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
import elkLayouts from "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs";

mermaid.registerLayoutLoaders(elkLayouts);
mermaid.initialize({
  startOnLoad: false,
  securityLevel: "loose",
});

// Make our configured instance visible to Zensical's Mermaid integration.
window.mermaid = mermaid;
