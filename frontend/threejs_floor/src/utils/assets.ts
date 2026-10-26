/** Asset loading utilities */

import * as THREE from 'three';

export interface SpriteFrame {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface SpriteSheetData {
  frames: Record<string, SpriteFrame>;
  meta: { image: string; size: { w: number; h: number } };
}

export interface LoadResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}

const CACHE = new Map<string, any>();

/** Load JSON with caching */
export async function loadJSON<T>(url: string): Promise<LoadResult<T>> {
  if (CACHE.has(url)) return { success: true, data: CACHE.get(url) };
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    CACHE.set(url, data);
    return { success: true, data };
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : String(e) };
  }
}

/** Load image as HTMLImageElement */
export function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
    img.src = url;
  });
}

/** Load texture with Three.js */
export function loadTexture(url: string, renderer?: THREE.WebGLRenderer): Promise<THREE.Texture> {
  return new Promise((resolve, reject) => {
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin('anonymous');
    loader.load(
      url,
      (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.magFilter = THREE.NearestFilter; // Pixel art crisp
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.generateMipmaps = true;
        if (renderer) texture.needsUpdate = true;
        resolve(texture);
      },
      undefined,
      (err) => reject(err)
    );
  });
}

/** Create a sprite material from texture atlas */
export function createSpriteMaterial(
  texture: THREE.Texture,
  _frame: SpriteFrame,
  options: { transparent?: boolean; alphaTest?: number; depthWrite?: boolean } = {}
): THREE.SpriteMaterial {
  const { transparent = true, alphaTest = 0.1, depthWrite = false } = options;
  // We use a custom shader to crop the texture to the frame
  // For simplicity, we'll use a plane geometry with UV offset instead of Sprite
  return new THREE.SpriteMaterial({
    map: texture,
    transparent,
    alphaTest,
    depthWrite,
    rotation: 0,
  });
}

/** Create a plane geometry with UV mapping for a specific frame */
export function createFrameGeometry(
  frame: SpriteFrame,
  textureSize: { w: number; h: number },
  worldSize: number = 1
): THREE.PlaneGeometry {
  const u0 = frame.x / textureSize.w;
  const v0 = frame.y / textureSize.h;
  const u1 = (frame.x + frame.w) / textureSize.w;
  const v1 = (frame.y + frame.h) / textureSize.h;

  const geom = new THREE.PlaneGeometry(worldSize, worldSize);
  // UV coordinates: bottom-left, bottom-right, top-right, top-left
  geom.setAttribute('uv', new THREE.Float32BufferAttribute([
    u0, v1,  // bottom-left
    u1, v1,  // bottom-right
    u1, v0,  // top-right
    u0, v0,  // top-left
  ], 2));
  return geom;
}

/** Create mesh for a sprite frame */
export function createFrameMesh(
  texture: THREE.Texture,
  frame: SpriteFrame,
  textureSize: { w: number; h: number },
  worldSize: number = 1,
  options: { side?: THREE.Side; transparent?: boolean; alphaTest?: number } = {}
): THREE.Mesh {
  const { side = THREE.DoubleSide, transparent = true, alphaTest = 0.1 } = options;
  const geom = createFrameGeometry(frame, textureSize, worldSize);
  const mat = new THREE.MeshBasicMaterial({
    map: texture,
    transparent,
    alphaTest,
    side,
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(geom, mat);
  // Sprite faces camera
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

/** Load spritesheet (image + JSON) */
export async function loadSpriteSheet(
  imageUrl: string,
  jsonUrl: string
): Promise<{ texture: THREE.Texture; data: SpriteSheetData }> {
  const [texture, jsonResult] = await Promise.all([
    loadTexture(imageUrl),
    loadJSON<SpriteSheetData>(jsonUrl),
  ]);
  if (!jsonResult.success || !jsonResult.data) {
    throw new Error(`Failed to load spritesheet JSON: ${jsonResult.error}`);
  }
  return { texture, data: jsonResult.data };
}

/** Create placeholder texture for development */
export function createPlaceholderTexture(color: number, size: number = 64): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
  ctx.fillRect(0, 0, size, size);
  // Add a subtle pattern
  ctx.strokeStyle = '#ffffff22';
  ctx.lineWidth = 1;
  for (let i = 0; i < size; i += 8) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i, size);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, i);
    ctx.lineTo(size, i);
    ctx.stroke();
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  return texture;
}

/** Create placeholder avatar texture (Habbo-style) */
export function createAvatarTexture(
  bodyColor: number,
  type: 'operator' | 'chief' | 'agent',
  size: number = 64
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = size * 2; // 2x for retina
  canvas.height = size * 3;
  const ctx = canvas.getContext('2d')!;
  ctx.scale(2, 2);
  const s = size;

  // Skin tone
  const skin = '#ffe0bd';
  const outline = '#ccaa88';

  // Head
  ctx.fillStyle = skin;
  ctx.strokeStyle = outline;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(s/2 - 6, 6, 12, 12, 3);
  ctx.fill();
  ctx.stroke();
  // Eyes
  ctx.fillStyle = '#1a1a2e';
  ctx.beginPath(); ctx.arc(s/2 - 3, 10, 2, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(s/2 + 3, 10, 2, 0, Math.PI * 2); ctx.fill();

  // Torso
  const bodyHex = `#${bodyColor.toString(16).padStart(6, '0')}`;
  ctx.fillStyle = bodyHex;
  ctx.strokeStyle = lightenColorHex(bodyColor, 30);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(s/2 - 8, 20, 16, 14, 2);
  ctx.fill();
  ctx.stroke();

  // Legs
  ctx.fillStyle = '#1a1a2e';
  ctx.beginPath(); ctx.roundRect(s/2 - 5, 34, 4, 10, 1); ctx.fill();
  ctx.beginPath(); ctx.roundRect(s/2 + 1, 34, 4, 10, 1); ctx.fill();

  // Accent border
  if (type === 'chief') {
    ctx.strokeStyle = '#ffcc00';
    ctx.lineWidth = 2;
    ctx.strokeRect(2, 2, s - 4, s * 1.5 - 4);
  } else if (type === 'operator') {
    ctx.strokeStyle = '#4488ff';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(2, 2, s - 4, s * 1.5 - 4);
  } else {
    ctx.strokeStyle = lightenColorHex(bodyColor, 40);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(2, 2, s - 4, s * 1.5 - 4);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  return texture;
}

/** Lighten a hex color by percentage */
function lightenColorHex(hex: number, percent: number): string {
  const r = Math.min(255, ((hex >> 16) & 255) + Math.round(255 * percent / 100));
  const g = Math.min(255, ((hex >> 8) & 255) + Math.round(255 * percent / 100));
  const b = Math.min(255, (hex & 255) + Math.round(255 * percent / 100));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

/** Preload all assets */
export async function preloadAssets(): Promise<{
  textures: Map<string, THREE.Texture>;
  spritesheets: Map<string, { texture: THREE.Texture; data: any }>;
}> {
  const textures = new Map<string, THREE.Texture>();
  const spritesheets = new Map<string, { texture: THREE.Texture; data: any }>();

  // Create placeholder textures for development
  textures.set('avatar_operator', createAvatarTexture(0x4488ff, 'operator'));
  textures.set('avatar_chief', createAvatarTexture(0xffcc00, 'chief'));
  textures.set('avatar_research', createAvatarTexture(0x0066ff, 'agent'));
  textures.set('avatar_validation', createAvatarTexture(0x00ccaa, 'agent'));
  textures.set('avatar_execution', createAvatarTexture(0x00cc66, 'agent'));
  textures.set('avatar_guardian', createAvatarTexture(0xff8800, 'agent'));
  textures.set('avatar_regime', createAvatarTexture(0x8844ff, 'agent'));
  textures.set('avatar_alpha', createAvatarTexture(0xffcc00, 'agent'));

  // Zone floor textures
  textures.set('zone_research', createPlaceholderTexture(0x0066ff));
  textures.set('zone_validation', createPlaceholderTexture(0x00ccaa));
  textures.set('zone_execution', createPlaceholderTexture(0x00cc66));
  textures.set('zone_guardian', createPlaceholderTexture(0xff8800));
  textures.set('zone_regime', createPlaceholderTexture(0x8844ff));
  textures.set('zone_alpha', createPlaceholderTexture(0xffcc00));
  textures.set('zone_chief', createPlaceholderTexture(0x0d0d12));
  textures.set('zone_corridor', createPlaceholderTexture(0x0d0d12));
  textures.set('zone_entrance', createPlaceholderTexture(0x1a1a2e));
  textures.set('zone_south', createPlaceholderTexture(0x0d0d12));

  return { textures, spritesheets };
}