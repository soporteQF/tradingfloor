/** Isometric projection helpers (2:1 ratio) */

export const TILE_W = 64;
export const TILE_H = 32;

export interface Vec2 { x: number; y: number; }
export interface Vec3 { x: number; y: number; z: number; }

/** Grid (tile) coordinates to isometric screen coordinates */
export function gridToScreen(gx: number, gy: number): Vec2 {
  return {
    x: (gx - gy) * (TILE_W / 2),
    y: (gx + gy) * (TILE_H / 2),
  };
}

/** Isometric screen coordinates to grid (tile) coordinates */
export function screenToGrid(sx: number, sy: number): Vec2 {
  return {
    x: (sx / (TILE_W / 2) + sy / (TILE_H / 2)) / 2,
    y: (sy / (TILE_H / 2) - sx / (TILE_W / 2)) / 2,
  };
}

/** World (3D) coordinates to isometric screen coordinates */
export function worldToScreen(wx: number, _wy: number, wz: number = 0): Vec2 {
  // In our coordinate system: world X = grid X, world Z = grid Y
  // Y is height
  const sx = (wx - wz) * (TILE_W / 2);
  const sy = (wx + wz) * (TILE_H / 2) - wz * 0.5; // height offset
  return { x: sx, y: sy };
}

/** Get 4 corners of an isometric rectangle in screen space */
export function getIsoRect(px: number, py: number, w: number, h: number): number[] {
  const corners = [
    gridToScreen(px / TILE_W, py / TILE_H),
    gridToScreen((px + w) / TILE_W, py / TILE_H),
    gridToScreen((px + w) / TILE_W, (py + h) / TILE_H),
    gridToScreen(px / TILE_W, (py + h) / TILE_H),
  ];
  return corners.flatMap(p => [p.x, p.y]);
}

/** Get 4 corners of an isometric rectangle in world space */
export function getIsoRectWorld(gx: number, gy: number, gw: number, gh: number): Vec2[] {
  return [
    gridToScreen(gx, gy),
    gridToScreen(gx + gw, gy),
    gridToScreen(gx + gw, gy + gh),
    gridToScreen(gx, gy + gh),
  ];
}

/** Check if a grid point is inside a zone */
export function isInZone(gx: number, gy: number, zone: { x: number; y: number; w: number; h: number }): boolean {
  return gx >= zone.x && gx < zone.x + zone.w && gy >= zone.y && gy < zone.y + zone.h;
}

/** Check if a grid point is inside the chief center */
export function isInChiefCenter(gx: number, gy: number, chief: { x: number; y: number; size: number }): boolean {
  return gx >= chief.x && gx < chief.x + chief.size && gy >= chief.y && gy < chief.y + chief.size;
}

/** Get zone at grid position */
export function getZoneAt(gx: number, gy: number, zones: Record<string, { x: number; y: number; w: number; h: number }>): string | null {
  for (const [key, zone] of Object.entries(zones)) {
    if (isInZone(gx, gy, zone)) return key;
  }
  return null;
}

/** Lerp helper */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Lerp Vec2 */
export function lerpVec2(a: Vec2, b: Vec2, t: number): Vec2 {
  return { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) };
}

/** Clamp */
export function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

/** Distance between two grid points */
export function gridDistance(ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  return Math.sqrt(dx * dx + dy * dy);
}

// Type declaration for Three.js (avoid importing full three in utils)
interface ThreeColor {
  setHex(hex: number): this;
}

/** Convert hex color to Three.js Color-like object */
export function hexToThreeColor(hex: number): { setHex: (hex: number) => any } {
  return { setHex: (h: number) => ({ r: (h >> 16 & 255) / 255, g: (h >> 8 & 255) / 255, b: (h & 255) / 255 }) };
}

/** Create a color with alpha for Three.js materials */
export function colorWithAlpha(hex: number, _alpha: number): { setHex: (hex: number) => any } {
  return hexToThreeColor(hex);
}