/** Habbo-style floor tiles - bright, visible, authentic look */

export function createHabboFloorTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  // Habbo classic floor colors - bright, visible
  const LIGHT_TILE = '#d4d4c8';      // Light beige tile
  const DARK_TILE = '#b8b8a8';       // Slightly darker tile
  const GRID_COLOR = '#ffffff44';    // Subtle white grid
  const EDGE_LIGHT = '#ffffff88';    // Top/left edge highlight
  const EDGE_DARK = '#88887788';     // Bottom/right edge shadow

  // Draw 4x2 tile pattern (each tile = 64x32 in iso space)
  for (let row = 0; row < 2; row++) {
    for (let col = 0; col < 4; col++) {
      const cx = 32 + col * 64;
      const cy = 16 + row * 32;
      const isLight = (row + col) % 2 === 0;
      const fill = isLight ? LIGHT_TILE : DARK_TILE;
      
      // Diamond shape
      ctx.beginPath();
      ctx.moveTo(cx, cy - 16);
      ctx.lineTo(cx + 32, cy);
      ctx.lineTo(cx, cy + 16);
      ctx.lineTo(cx - 32, cy);
      ctx.closePath();
      
      ctx.fillStyle = fill;
      ctx.fill();
      
      // 3D edges - Habbo style
      ctx.lineWidth = 1;
      // Top-left edges (lighter)
      ctx.strokeStyle = EDGE_LIGHT;
      ctx.beginPath();
      ctx.moveTo(cx - 32, cy);
      ctx.lineTo(cx, cy - 16);
      ctx.lineTo(cx + 32, cy);
      ctx.stroke();
      
      // Bottom-right edges (darker)
      ctx.strokeStyle = EDGE_DARK;
      ctx.beginPath();
      ctx.moveTo(cx + 32, cy);
      ctx.lineTo(cx, cy + 16);
      ctx.lineTo(cx - 32, cy);
      ctx.stroke();
    }
  }

  // Subtle grid overlay
  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = 0.5;
  for (let i = 0; i < 256; i += 32) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 128); ctx.stroke();
  }
  for (let j = 0; j < 128; j += 16) {
    ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(256, j); ctx.stroke();
  }

  return canvas;
}

/** Zone accent colors - bright, Habbo-style pastels */
export const ZONE_COLORS = {
  research:    { floor: '#4a90d9', accent: '#6bb3ff', name: 'RESEARCH' },
  validation:  { floor: '#4ad9a0', accent: '#6bffc8', name: 'VALIDATION' },
  execution:   { floor: '#d9a04a', accent: '#ffc86b', name: 'EXECUTION' },
  guardian:    { floor: '#d94a4a', accent: '#ff6b6b', name: 'GUARDIAN' },
  regime:      { floor: '#a04ad9', accent: '#c86bff', name: 'REGIME' },
  alpha:       { floor: '#4ad9d9', accent: '#6bffff', name: 'ALPHA' },
} as const;

/** Create zone floor texture with accent border */
export function createZoneFloorTexture(baseColor: string, accentColor: string): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  // Base floor with zone tint
  const baseLight = lightenColor(baseColor, 40);
  const baseDark = lightenColor(baseColor, 20);

  for (let row = 0; row < 2; row++) {
    for (let col = 0; col < 4; col++) {
      const cx = 32 + col * 64;
      const cy = 16 + row * 32;
      const isLight = (row + col) % 2 === 0;
      const fill = isLight ? baseLight : baseDark;
      
      ctx.beginPath();
      ctx.moveTo(cx, cy - 16);
      ctx.lineTo(cx + 32, cy);
      ctx.lineTo(cx, cy + 16);
      ctx.lineTo(cx - 32, cy);
      ctx.closePath();
      
      ctx.fillStyle = fill;
      ctx.fill();
      
      // Edges
      ctx.lineWidth = 1;
      ctx.strokeStyle = '#ffffff66';
      ctx.beginPath();
      ctx.moveTo(cx - 32, cy);
      ctx.lineTo(cx, cy - 16);
      ctx.lineTo(cx + 32, cy);
      ctx.stroke();
      
      ctx.strokeStyle = '#00000044';
      ctx.beginPath();
      ctx.moveTo(cx + 32, cy);
      ctx.lineTo(cx, cy + 16);
      ctx.lineTo(cx - 32, cy);
      ctx.stroke();
    }
  }

  // Accent border around zone (subtle)
  ctx.strokeStyle = accentColor + '88';
  ctx.lineWidth = 2;
  // Draw zone perimeter in texture space
  const hw = 128, hh = 64;
  ctx.beginPath();
  ctx.moveTo(128, 0);
  ctx.lineTo(256, 64);
  ctx.lineTo(128, 128);
  ctx.lineTo(0, 64);
  ctx.closePath();
  ctx.stroke();

  return canvas;
}

/** Chief podium texture */
export function createChiefPodiumTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  // Gold/amber podium base
  const baseColor = '#c8a030';
  const lightColor = '#e8c050';
  const darkColor = '#987020';

  // Podium shape (centered)
  const cx = 128, cy = 64;
  const w = 120, h = 60;

  ctx.beginPath();
  ctx.moveTo(cx, cy - h/2);
  ctx.lineTo(cx + w/2, cy);
  ctx.lineTo(cx, cy + h/2);
  ctx.lineTo(cx - w/2, cy);
  ctx.closePath();
  
  // Gradient fill
  const grad = ctx.createLinearGradient(cx - w/2, cy - h/2, cx + w/2, cy + h/2);
  grad.addColorStop(0, lightColor);
  grad.addColorStop(0.5, baseColor);
  grad.addColorStop(1, darkColor);
  ctx.fillStyle = grad;
  ctx.fill();

  // Gold accent rim
  ctx.strokeStyle = '#ffd700';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(cx, cy - h/2);
  ctx.lineTo(cx + w/2, cy);
  ctx.lineTo(cx, cy + h/2);
  ctx.lineTo(cx - w/2, cy);
  ctx.closePath();
  ctx.stroke();

  // Inner glow lines
  ctx.strokeStyle = '#ffd70088';
  ctx.lineWidth = 1;
  for (let i = 1; i < 4; i++) {
    const inset = i * 8;
    ctx.beginPath();
    ctx.moveTo(cx, cy - h/2 + inset);
    ctx.lineTo(cx + w/2 - inset, cy);
    ctx.lineTo(cx, cy + h/2 - inset);
    ctx.lineTo(cx - w/2 + inset, cy);
    ctx.closePath();
    ctx.stroke();
  }

  return canvas;
}

/** Corridor texture */
export function createCorridorTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#2a2a2a';
  ctx.fillRect(0, 0, 256, 64);

  // Directional arrows
  ctx.strokeStyle = '#00ff88';
  ctx.lineWidth = 2;
  for (let x = 16; x < 256; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x - 8, 32);
    ctx.lineTo(x, 24);
    ctx.lineTo(x + 8, 32);
    ctx.moveTo(x, 24);
    ctx.lineTo(x, 40);
    ctx.stroke();
  }

  return canvas;
}

/** Entrance texture */
export function createEntranceTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, 256, 128);

  // Welcome mat area
  ctx.fillStyle = '#2a2a3e';
  ctx.fillRect(64, 32, 128, 64);

  // Door outline
  ctx.strokeStyle = '#00ff88';
  ctx.lineWidth = 3;
  ctx.strokeRect(80, 24, 96, 80);

  return canvas;
}

/** South support texture */
export function createSouthSupportTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(0, 0, 256, 128);

  // Grid lines
  ctx.strokeStyle = '#333333';
  ctx.lineWidth = 1;
  for (let i = 0; i < 256; i += 16) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 128); ctx.stroke();
  }
  for (let j = 0; j < 128; j += 16) {
    ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(256, j); ctx.stroke();
  }

  return canvas;
}

function lightenColor(hex: string, amount: number): string {
  const c = hex.replace('#', '');
  const r = Math.min(255, parseInt(c.slice(0, 2), 16) + amount);
  const g = Math.min(255, parseInt(c.slice(2, 4), 16) + amount);
  const b = Math.min(255, parseInt(c.slice(4, 6), 16) + amount);
  return `rgb(${r},${g},${b})`;
}

function darkenColor(hex: string, amount: number): string {
  const c = hex.replace('#', '');
  const r = Math.max(0, parseInt(c.slice(0, 2), 16) - amount);
  const g = Math.max(0, parseInt(c.slice(2, 4), 16) - amount);
  const b = Math.max(0, parseInt(c.slice(4, 6), 16) - amount);
  return `rgb(${r},${g},${b})`;
}