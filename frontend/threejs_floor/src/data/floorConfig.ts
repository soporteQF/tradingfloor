/** Single source of truth for floor layout, zones, colors, positions */

export const TILE_W = 64;
export const TILE_H = 32;
export const GRID_W = 80;
export const GRID_H = 60;
export const ZONE_SIZE = 16;
export const CORRIDOR_W = 4;

export type ZoneKey = 'research' | 'validation' | 'execution' | 'guardian' | 'regime' | 'alpha';

export interface ZoneConfig {
  key: ZoneKey;
  name: string;
  color: number;
  accent: number;
  emoji: string;
  desc: string;
  x: number;
  y: number;
}

export const ZONES: Record<ZoneKey, ZoneConfig> = {
  research: {
    key: 'research',
    name: 'RESEARCH',
    color: 0x0066ff,
    accent: 0x0099ff,
    emoji: '🔬',
    desc: 'Discovery Lab · Pattern Mine · Hypothesis Queue',
    x: 8,
    y: 8,
  },
  validation: {
    key: 'validation',
    name: 'VALIDATION',
    color: 0x00ccaa,
    accent: 0x00ffdd,
    emoji: '⚖️',
    desc: 'Walk-Forward Chamber · Monte Carlo · Referee',
    x: 26,
    y: 8,
  },
  execution: {
    key: 'execution',
    name: 'EXECUTION',
    color: 0x00cc66,
    accent: 0x00ff88,
    emoji: '💰',
    desc: 'Order Desk · Risk Check · Fill Tracker',
    x: 44,
    y: 8,
  },
  guardian: {
    key: 'guardian',
    name: 'GUARDIAN',
    color: 0xff8800,
    accent: 0xffaa00,
    emoji: '🛡️',
    desc: 'Shield Vault · 8 Guards · Kill Switch',
    x: 44,
    y: 36,
  },
  regime: {
    key: 'regime',
    name: 'REGIME',
    color: 0x8844ff,
    accent: 0xaa66ff,
    emoji: '🌊',
    desc: 'HMM 4-State · Probability Bars · Transitions',
    x: 26,
    y: 36,
  },
  alpha: {
    key: 'alpha',
    name: 'ALPHA LIBRARY',
    color: 0xffcc00,
    accent: 0xffdd44,
    emoji: '🧠',
    desc: 'Knowledge Graph · Playbooks · Causal Paths',
    x: 8,
    y: 36,
  },
};

export const ZONE_KEYS: ZoneKey[] = ['research', 'validation', 'execution', 'guardian', 'regime', 'alpha'];

export const CHIEF_CENTER = { x: 32, y: 22, size: 12 };
export const ENTRANCE = { x: 30, y: 0, w: 20, h: 6 };
export const CORRIDOR_Y = 24;
export const SOUTH_SUPPORT_Y = 48;

export const OPERATOR_START = { x: 32, y: 28 };
export const CHIEF_POS = { x: CHIEF_CENTER.x + CHIEF_CENTER.size / 2, y: CHIEF_CENTER.y + CHIEF_CENTER.size / 2 };

// Avatar types
export type AvatarType = 'operator' | 'chief' | ZoneKey;

export const AVATAR_COLORS: Record<AvatarType, number> = {
  operator: 0x4488ff,
  chief: 0xffcc00,
  research: 0x0066ff,
  validation: 0x00ccaa,
  execution: 0x00cc66,
  guardian: 0xff8800,
  regime: 0x8844ff,
  alpha: 0xffcc00,
};

// Camera
export const CAMERA_DEFAULTS = {
  zoom: 1,
  minZoom: 0.3,
  maxZoom: 3,
  lerpFactor: 0.08,
  offsetX: -0.15, // screen fraction
  offsetY: -0.1,
};

// Lighting
export const LIGHTING = {
  ambient: { color: 0x444466, intensity: 0.6 },
  directional: { color: 0xffffff, intensity: 1.2, position: [100, 200, 100] },
  hemisphere: { skyColor: 0x00d4aa, groundColor: 0x0a0a0f, intensity: 0.4 },
  zoneAccent: { intensity: 0.3, distance: 200, decay: 2 },
};

// Post-processing
export const POST_PROCESSING = {
  bloom: { strength: 0.3, radius: 0.5, threshold: 0.8 },
  scanlines: { opacity: 0.08, scale: 1024 },
  vignette: { offset: 0.5, darkness: 0.3 },
};

// Reduced motion
export const REDUCED_MOTION_DEFAULTS = {
  disableBloom: true,
  disableScanlines: true,
  disableCameraLerp: true,
  disableAvatarBob: true,
  disableParticles: true,
};

// Asset paths
export const ASSET_PATHS = {
  sprites: {
    tiles: '/assets/sprites/tiles.png',
    avatars: '/assets/sprites/avatars.png',
    ui: '/assets/sprites/ui.png',
  },
  models: {
    // Future: GLTF props
  },
  json: {
    tileset: '/assets/sprites/tiles.json',
    avatars: '/assets/sprites/avatars.json',
    ui: '/assets/sprites/ui.json',
  },
};

// API
export const API_BASE = '/api';
export const POLL_INTERVAL_MS = 2000;