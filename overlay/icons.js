// icons.js — original stylized SVG icon set for ASCIIMUD theatrical overlay.
//
// All icons are hand-drawn here, no third-party assets, no attribution
// required. Designed as 24×24 viewBox monochrome glyphs that get colored by
// CSS `currentColor`. Drop in PNGs/SVGs at overlay/icons/<name>.svg later
// to override; iconUrlFor() will prefer that path if present.

const ICONS = {
  // ---- schools ----
  physical: `<path d="M5 19 L19 5 M14 5 H19 V10 M5 14 L10 19" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`,
  holy:     `<circle cx="12" cy="12" r="4" fill="currentColor"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v4M12 18v4M2 12h4M18 12h4M5 5l3 3M16 16l3 3M19 5l-3 3M5 19l3-3"/></g>`,
  fire:     `<path d="M12 22 C5 18 6 12 9 9 C9 12 11 11 11 9 C11 6 9 5 12 2 C12 6 18 8 18 14 C18 19 15 22 12 22 Z" fill="currentColor"/>`,
  frost:    `<g stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"><path d="M12 2v20M3 7l18 10M3 17l18-10"/><path d="M9 4l3 3 3-3M9 20l3-3 3 3M2 10l3 1 -1 3M22 10l-3 1 1 3M2 14l3-1 -1-3M22 14l-3-1 1-3"/></g>`,
  nature:   `<path d="M4 20 C4 10 12 4 20 4 C20 12 14 20 4 20 Z" fill="currentColor"/><path d="M4 20 L14 10" stroke="#0a0805" stroke-width="1.5"/>`,
  shadow:   `<circle cx="12" cy="12" r="8" fill="currentColor"/><circle cx="12" cy="12" r="4" fill="#0a0805"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/>`,
  arcane:   `<g fill="currentColor"><path d="M12 2 L13 10 L21 12 L13 14 L12 22 L11 14 L3 12 L11 10 Z"/><circle cx="12" cy="12" r="1.5" fill="#0a0805"/></g>`,
  generic:  `<rect x="5" y="5" width="14" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 12h6M12 9v6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>`,

  // ---- classes ----
  warrior:  `<path d="M12 2 L15 8 L21 9 L17 13 L18 19 L12 16 L6 19 L7 13 L3 9 L9 8 Z" fill="currentColor"/>`,
  paladin:  `<g fill="currentColor"><path d="M11 2h2v8h6v2h-6v10h-2V12H5v-2h6z"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/></g>`,
  hunter:   `<g stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"><path d="M3 21 L21 3"/><path d="M21 3 L17 3 L17 7"/><path d="M3 21 L7 21 L7 17"/><circle cx="12" cy="12" r="6"/></g>`,
  rogue:    `<g fill="currentColor"><path d="M14 3 L21 10 L11 20 L8 17 L18 7 Z"/><path d="M3 21 L8 16 L10 18 L5 23 Z" transform="translate(0 -2)"/></g>`,
  priest:   `<g fill="currentColor"><path d="M11 2h2v6h6v2h-6v12h-2V10H5V8h6z"/></g>`,
  shaman:   `<g fill="currentColor"><path d="M12 2 L4 8 L4 22 L20 22 L20 8 Z"/><circle cx="12" cy="13" r="3" fill="#0a0805"/></g>`,
  mage:     `<g fill="currentColor"><path d="M3 21 L18 6 L21 9 L6 24 Z" transform="translate(0 -2)"/><path d="M18 4 L20 6 L18 8 L16 6 Z M5 11 L7 13 L5 15 L3 13 Z"/></g>`,
  warlock:  `<g fill="currentColor"><circle cx="12" cy="10" r="6"/><path d="M6 22 L12 14 L18 22 Z"/></g><g fill="#0a0805"><circle cx="9.5" cy="9" r="1.2"/><circle cx="14.5" cy="9" r="1.2"/></g>`,
  druid:    `<g fill="currentColor"><path d="M4 16 C6 8 10 6 12 4 C14 6 18 8 20 16 C18 13 14 12 12 16 C10 12 6 13 4 16 Z"/><path d="M12 16 L12 22" stroke="currentColor" stroke-width="2"/></g>`,

  // ---- tags ----
  buff:     `<g stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none"><path d="M12 4v16M4 12h16"/></g>`,
  debuff:   `<g stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none"><path d="M5 12h14"/></g>`,
  cooldown: `<g fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 3" stroke-linecap="round"/></g>`,
  empty:    `<rect x="4" y="4" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 2" opacity="0.5"/>`,
};

const SCHOOL_COLORS = {
  physical: "#d4d4d4",
  holy:     "#fde68a",
  fire:     "#fb923c",
  frost:    "#7dd3fc",
  nature:   "#4ade80",
  shadow:   "#a78bfa",
  arcane:   "#f0abfc",
  generic:  "#94a3b8",
};

const CLASS_COLORS = {
  Warrior:  "#c79c6e",
  Paladin:  "#f58cba",
  Hunter:   "#abd473",
  Rogue:    "#fff569",
  Priest:   "#ffffff",
  Shaman:   "#0070de",
  Mage:     "#69ccf0",
  Warlock:  "#9482c9",
  Druid:    "#ff7d0a",
};

function svgWrap(name, color) {
  const body = ICONS[name] || ICONS.generic;
  const c = color || "currentColor";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" style="color:${c};width:100%;height:100%">${body}</svg>`;
}

// Inferred from a WoW icon filename like "spell_fire_flamebolt".
function schoolFromIconName(iconName) {
  if (!iconName) return "generic";
  const n = iconName.toLowerCase();
  if (n.includes("fire"))                          return "fire";
  if (n.includes("frost"))                         return "frost";
  if (n.includes("nature") || n.includes("heal")
      || n.includes("lightning"))                  return "nature";
  if (n.includes("shadow") || n.includes("death")) return "shadow";
  if (n.includes("holy")   || n.includes("light")) return "holy";
  if (n.includes("arcane") || n.includes("magic")) return "arcane";
  return "physical";
}

function iconForSpell(meta) {
  const school = (meta && meta.school) || schoolFromIconName(meta && meta.icon);
  return { svg: svgWrap(school, SCHOOL_COLORS[school]), school };
}

function iconForClass(cls) {
  const key = (cls || "").toLowerCase();
  return svgWrap(key, CLASS_COLORS[cls] || "#d4af37");
}

function iconForTag(tag) {
  return svgWrap(tag, tag === "debuff" ? "#fca5a5" : "#fde68a");
}

window.ICONS = { svgWrap, iconForSpell, iconForClass, iconForTag,
                 SCHOOL_COLORS, CLASS_COLORS };
