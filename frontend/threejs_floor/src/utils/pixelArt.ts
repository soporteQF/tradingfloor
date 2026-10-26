/** Pixel-art texture generators (Habbo / cyberpunk style).
 *  All canvases use hard pixels (no smoothing) for the authentic look. */

/** A 2x2 arrangement of isometric tile diamonds (checkerboard) — 128x64 px.
 *  In shape-space one repetition of this texture covers 128x64 units = 2x2 tiles. */
export function createHabboTileTexture(baseColor: number, altColor: number, outlineLight: string, outlineDark: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const base = hexToCss(baseColor);
  const alt = hexToCss(altColor);

  for (let row = 0; row < 2; row++) {
    for (let col = 0; col < 2; col++) {
      const cx = 32 + col * 64;
      const cy = 16 + row * 32;
      const fill = (row + col) % 2 === 0 ? base : alt;
      drawIsoTile(ctx, cx, cy, fill, outlineLight, outlineDark);
    }
  }
  return canvas;
}

function drawIsoTile(ctx: CanvasRenderingContext2D, cx: number, cy: number, fill: string, outlineLight: string, outlineDark: string): void {
  // Diamond: (cx, cy-16) (cx+32, cy) (cx, cy+16) (cx-32, cy)
  ctx.beginPath();
  ctx.moveTo(cx, cy - 16);
  ctx.lineTo(cx + 32, cy);
  ctx.lineTo(cx, cy + 16);
  ctx.lineTo(cx - 32, cy);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();

  // Habbo-style edge shading: light top-left edges, dark bottom-right edges
  ctx.lineWidth = 1;
  ctx.strokeStyle = outlineLight;
  ctx.beginPath();
  ctx.moveTo(cx - 32, cy);
  ctx.lineTo(cx, cy - 16);
  ctx.lineTo(cx + 32, cy);
  ctx.stroke();

  ctx.strokeStyle = outlineDark;
  ctx.beginPath();
  ctx.moveTo(cx + 32, cy);
  ctx.lineTo(cx, cy + 16);
  ctx.lineTo(cx - 32, cy);
  ctx.stroke();
}

/** Dark tech floor with grid + subtle scanline rows (for corridor / support areas) */
export function createTechFloorTexture(accentCss: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = '#0d0d12';
  ctx.fillRect(0, 0, 128, 64);

  ctx.strokeStyle = accentCss;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.25;
  for (let i = 0; i < 128; i += 16) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 64); ctx.stroke();
  }
  for (let j = 0; j < 64; j += 16) {
    ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(128, j); ctx.stroke();
  }
  ctx.globalAlpha = 0.6;
  ctx.strokeStyle = accentCss;
  ctx.strokeRect(0.5, 0.5, 127, 63);
  ctx.globalAlpha = 1;
  return canvas;
}

/** Emissive monitor screen: green candlestick chart on dark bg */
export function createMonitorTexture(variant: 'green' | 'blue' | 'purple'): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 24;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const palette = {
    green: { bg: '#04150d', line: '#00ff88', bar: '#00cc66', barAlt: '#ff4757' },
    blue: { bg: '#040d1a', line: '#3aa5ff', bar: '#0099ff', barAlt: '#ff4757' },
    purple: { bg: '#0f0418', line: '#aa66ff', bar: '#8844ff', barAlt: '#ff4757' },
  }[variant];

  ctx.fillStyle = palette.bg;
  ctx.fillRect(0, 0, 32, 24);

  // Grid lines
  ctx.strokeStyle = '#ffffff0d';
  for (let y = 4; y < 24; y += 5) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(32, y); ctx.stroke(); }

  // Candles
  let x = 2;
  let price = 10 + Math.random() * 4;
  while (x < 30) {
    const delta = (Math.random() - 0.48) * 5;
    const prev = price;
    price = Math.max(3, Math.min(20, price + delta));
    const up = price >= prev;
    ctx.fillStyle = up ? palette.bar : palette.barAlt;
    const top = Math.min(prev, price) | 0;
    const h = Math.max(1, Math.abs(price - prev) | 0);
    ctx.fillRect(x, top, 2, h + 1);
    ctx.fillRect(x - 0.5, (price | 0), 3, 1);
    x += 4;
  }

  // Line overlay
  ctx.strokeStyle = palette.line;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(1, 20);
  ctx.lineTo(10, 14);
  ctx.lineTo(16, 17);
  ctx.lineTo(24, 8);
  ctx.lineTo(31, 5);
  ctx.stroke();
  return canvas;
}

/** Server rack front: LED dots grid */
export function createServerRackTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 16;
  canvas.height = 48;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = '#14141c';
  ctx.fillRect(0, 0, 16, 48);

  for (let y = 3; y < 48; y += 6) {
    ctx.fillStyle = '#1e1e2a';
    ctx.fillRect(1, y, 14, 4);
    // LEDs
    const led = Math.random() > 0.4 ? '#00ff88' : '#ffa502';
    ctx.fillStyle = led;
    ctx.fillRect(2, y + 1, 2, 2);
    if (Math.random() > 0.6) { ctx.fillStyle = '#3aa5ff'; ctx.fillRect(5, y + 1, 2, 2); }
    ctx.fillStyle = '#2a2a3a';
    ctx.fillRect(9, y + 1, 5, 2);
  }
  return canvas;
}

/** Wall texture: dark panel with accent top stripe */
export function createWallTexture(accentCss: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 16;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = '#14141c';
  ctx.fillRect(0, 0, 64, 16);
  // Panel seams
  ctx.fillStyle = '#1e1e2a';
  for (let x = 0; x < 64; x += 16) ctx.fillRect(x + 1, 2, 14, 12);
  // Accent stripe (top of the wall)
  ctx.fillStyle = accentCss;
  ctx.fillRect(0, 0, 64, 3);
  ctx.globalAlpha = 0.35;
  ctx.fillRect(0, 4, 64, 1);
  ctx.globalAlpha = 1;
  return canvas;
}

/** Avatar sprite: pixel person (head + torso + legs), 32x48 px */
export function createPixelAvatar(bodyColor: string, headColor: string, isChief: boolean): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 48;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const px = (x: number, y: number, w: number, h: number, c: string) => { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); };

  // Shadow
  ctx.fillStyle = '#00000055';
  ctx.beginPath(); ctx.ellipse(16, 46, 10, 3, 0, 0, Math.PI * 2); ctx.fill();

  // Legs
  px(11, 34, 4, 10, '#22222e');
  px(17, 34, 4, 10, '#22222e');
  px(11, 42, 4, 3, '#111118');
  px(17, 42, 4, 3, '#111118');

  // Torso
  px(9, 20, 14, 15, bodyColor);
  px(9, 20, 14, 2, shade(bodyColor, 30));       // shoulder highlight
  px(9, 33, 14, 2, shade(bodyColor, -25));      // torso shadow

  // Arms
  px(6, 21, 3, 11, shade(bodyColor, -15));
  px(23, 21, 3, 11, shade(bodyColor, -15));
  px(6, 31, 3, 2, headColor);
  px(23, 31, 3, 2, headColor);

  // Head
  px(10, 8, 12, 11, headColor);
  px(10, 8, 12, 2, shade(headColor, 25));
  // Eyes
  px(12, 13, 2, 2, '#0a0a0f');
  px(18, 13, 2, 2, '#0a0a0f');
  // Hair / cap
  px(10, 6, 12, 3, isChief ? '#ffcc00' : shade(bodyColor, -35));

  // Chief: shoulder pads + tie
  if (isChief) {
    px(7, 19, 4, 3, '#ffcc00');
    px(21, 19, 4, 3, '#ffcc00');
    px(14, 22, 4, 8, '#ff4757');
  }
  return canvas;
}

/** ---------- Isometric sprite drawing (Habbo pixel art style) ---------- */

/** Draw an iso box seen from 2:1 view, centered at (cx, cy) at base height.
 *  w: footprint width, d: footprint depth, h: screen height of the box. */
export function isoBox(ctx: CanvasRenderingContext2D,
  cx: number, cy: number, w: number, d: number, h: number,
  topFace: string, sideL: string, sideR: string): void {
  const hw = w / 2; const hd = d / 2; const vy = (w + d) / 2;
  const ty = cy - h - vy;

  // Top face (diamond)
  ctx.beginPath();
  ctx.moveTo(cx, ty);
  ctx.lineTo(cx + hw, ty + hd);
  ctx.lineTo(cx, ty + vy);
  ctx.lineTo(cx - hw, ty + hd);
  ctx.closePath();
  ctx.fillStyle = topFace;
  ctx.fill();

  // Right face
  ctx.beginPath();
  ctx.moveTo(cx + hw, ty + hd);
  ctx.lineTo(cx + hw, ty + hd + h);
  ctx.lineTo(cx, ty + vy + h);
  ctx.lineTo(cx, ty + vy);
  ctx.closePath();
  ctx.fillStyle = sideR;
  ctx.fill();

  // Left face
  ctx.beginPath();
  ctx.moveTo(cx - hw, ty + hd);
  ctx.lineTo(cx - hw, ty + hd + h);
  ctx.lineTo(cx, ty + vy + h);
  ctx.lineTo(cx, ty + vy);
  ctx.closePath();
  ctx.fillStyle = sideL;
  ctx.fill();
}

/** Draw a filled ellipse (circles/ovals in screen space). */
export function isoEllipse(ctx: CanvasRenderingContext2D,
  cx: number, cy: number, rx: number, ry: number, fill: string, stroke?: string): void {
  const kappa = 0.5522848;
  const ox = rx * kappa; const oy = ry * kappa;
  ctx.beginPath();
  ctx.moveTo(cx, cy - ry);
  ctx.bezierCurveTo(cx + ox, cy - ry, cx + rx, cy - oy, cx + rx, cy);
  ctx.bezierCurveTo(cx + rx, cy + oy, cx + ox, cy + ry, cx, cy + ry);
  ctx.bezierCurveTo(cx - ox, cy + ry, cx - rx, cy + oy, cx - rx, cy);
  ctx.bezierCurveTo(cx - rx, cy - oy, cx - ox, cy - ry, cx, cy - ry);
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
}

/** Draw a pixel line chart on a monitor face. */
export function drawChart(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number,
  color: string): void {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  let px = x; let py = y + h / 2;
  ctx.moveTo(px, py);
  for (let i = 1; i < 8; i++) {
    px += w / 8;
    py = y + h / 2 + Math.sin(i * 0.9) * h * 0.3;
    ctx.lineTo(px, py);
  }
  ctx.stroke();
}

/** Draw tiny glowing LED dots grid on a face (server rack style). */
export function drawLedGrid(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number,
  color1: string, color2: string): void {
  const rows = Math.max(1, Math.floor(h / 4));
  const cols = Math.max(1, Math.floor(w / 3));
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const dx = x + c * (w / cols) + 1;
      const dy = y + r * (h / rows) + 1;
      if (Math.random() > 0.35) {
        ctx.fillStyle = Math.random() > 0.5 ? color1 : color2;
        ctx.fillRect(dx, dy, 2, 2);
      }
    }
  }
}

// ---------- helpers ----------

export function hexToCss(hex: number): string {
  return `#${hex.toString(16).padStart(6, '0')}`;
}

export function css(hex: number): string {
  return hexToCss(hex);
}

/** Lighten (amount>0) or darken (amount<0) a CSS hex color */
export function shade(cssColor: string, amount: number): string {
  const m = cssColor.replace('#', '');
  const r = Math.max(0, Math.min(255, parseInt(m.slice(0, 2), 16) + amount));
  const g = Math.max(0, Math.min(255, parseInt(m.slice(2, 4), 16) + amount));
  const b = Math.max(0, Math.min(255, parseInt(m.slice(4, 6), 16) + amount));
  return `rgb(${r},${g},${b})`;
}
