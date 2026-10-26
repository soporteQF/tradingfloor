/** Pixel-art props builder: Habbo-style furniture as flat iso sprites.
 *  Everything renders as a 2D iso sprite lying flat on the XZ floor plane,
 *  exactly like Habbo renders its furniture. Nothing vertical is visible from
 *  a straight-down camera anyway, so pre-drawn iso sprites are the authentic
 *  approach. */

import * as THREE from 'three';
import {
  isoBox,
  isoEllipse,
  drawChart,
  drawLedGrid,
  css,
  createHabboTileTexture,
  createTechFloorTexture,
  createWallTexture,
  createMonitorTexture,
  createServerRackTexture,
} from '../utils/pixelArt.js';

export interface PropContext {
  gridToWorld: (gx: number, gy: number) => { x: number; y: number; z: number };
}

/** Build a flat sprite quad lying on the floor plane.
 *  Canvas top edge points toward screen-up (+z world). Sorted by renderOrder
 *  for painter's-algorithm iso layering (higher z drawn on top). */
export function spriteQuad(canvas: HTMLCanvasElement,
  worldW: number, worldH: number,
  x: number, y: number, z: number, renderOrder = 0): THREE.Mesh {
  const tex = new THREE.CanvasTexture(canvas);
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  const mat = new THREE.MeshBasicMaterial({
    map: tex,
    transparent: true,
    alphaTest: 0.08,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(worldW, worldH), mat);
  mesh.rotation.x = Math.PI / 2;
  mesh.position.set(x, y, z);
  mesh.renderOrder = renderOrder;
  return mesh;
}

/** Trading desk with 1-3 glowing monitors + chair. Canvas ~112x80 iso. */
export function buildDesk(monitorVariant: 'green' | 'blue' | 'purple' = 'green',
  monitors = 2): THREE.Group {
  const g = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 112; cvs.height = 80;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  // Shadow
  ctx.fillStyle = '#00000055';
  ctx.beginPath(); ctx.ellipse(56, 72, 22, 4, 0, 0, Math.PI * 2); ctx.fill();

  // Desk body (iso box, W=68 D=44 h=14) center (56, 62)
  isoBox(ctx, 56, 62, 68, 44, 14, '#1e1e2a', '#14141c', '#101016');

  // Accent strip along front edge
  ctx.fillStyle = '#00e5ff44';
  ctx.fillRect(42, 66, 28, 4);

  // Monitors
  const screenW = 12, screenH = 18;
  for (let i = 0; i < monitors; i++) {
    const mx = i === 0 ? 40 : 72;
    const my = 36;
    // monitor iso box (W=22 D=12 h=26)
    isoBox(ctx, mx, my, 22, 12, 26, '#14141c', '#0d0d12', '#0a1018');
    // screen on right face (sideR quad area)
    const sx = mx + 10; const sy = my + 6;
    ctx.fillStyle = '#04150d';
    ctx.fillRect(sx, sy, screenW, screenH);
    drawChart(ctx, sx + 1, sy + 2, screenW - 2, screenH - 4,
      monitorVariant === 'green' ? '#00ff88' :
        monitorVariant === 'blue' ? '#3aa5ff' : '#aa66ff');
  }

  // Chair behind desk (top = screen-up direction)
  isoBox(ctx, 56, 22, 24, 24, 12, '#22222e', '#161620', '#0f0f18');

  g.add(spriteQuad(cvs, 68, 52, 0, 4, 0, 10));
  return g;
}

/** Server rack with blinking LED front. Canvas 56x112 iso. */
export function buildServerRack(ledAccent: 'blue' | 'green' | 'purple' = 'blue'): THREE.Group {
  const g = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 56; cvs.height = 112;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#00000077';
  ctx.beginPath(); ctx.ellipse(28, 100, 14, 3, 0, 0, Math.PI * 2); ctx.fill();

  // Rack iso box (W=40 D=10 h=66)
  isoBox(ctx, 28, 92, 40, 10, 66, '#14141c', '#0d0d12', '#0a0a10');

  // LED grid on right face area
  const lx = 38; const ly = 38;
  drawLedGrid(ctx, lx + 2, ly + 6, 10, 56,
    ledAccent === 'blue' ? '#3aa5ff' :
      ledAccent === 'green' ? '#00ff88' : '#bd00ff',
    ledAccent === 'blue' ? '#004488' :
      ledAccent === 'green' ? '#006622' : '#660088');

  g.add(spriteQuad(cvs, 44, 72, 0, 2, 0, 10));
  return g;
}

/** Holographic dome: base ellipse + wireframe dome arcs + core glow. Canvas 112x88. */
export function buildHoloDome(accent: number): THREE.Group {
  const g = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 112; cvs.height = 88;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const accentCss = css(accent);

  // Shadow
  ctx.fillStyle = '#00000055';
  ctx.beginPath(); ctx.ellipse(56, 74, 30, 4, 0, 0, Math.PI * 2); ctx.fill();

  // Base ring
  isoEllipse(ctx, 56, 70, 30, 10, '#14141c');
  ctx.strokeStyle = '#1e1e2a';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.ellipse(56, 70, 30, 10, 0, 0, Math.PI * 2); ctx.stroke();

  // Dome wireframe arcs (purple/cyan)
  ctx.strokeStyle = accentCss;
  ctx.lineWidth = 1.5;
  ctx.globalAlpha = 0.5;
  for (let r = 10; r <= 32; r += 11) {
    ctx.beginPath(); ctx.ellipse(56, 40, r, r * 0.55, 0, 0, Math.PI); ctx.stroke();
  }
  for (let a = 0; a < 4; a++) {
    const ang = (a / 4) * Math.PI;
    const rx = 30 * Math.cos(ang); const ry = 16 * Math.sin(ang);
    ctx.beginPath();
    ctx.moveTo(56 + rx, 40);
    ctx.bezierCurveTo(56 + rx * 0.4, 40 - ry, 56 - rx * 0.4, 40 - ry, 56 - rx, 40);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Core glow
  const grad = ctx.createRadialGradient(56, 30, 0, 56, 30, 10);
  grad.addColorStop(0, accentCss);
  grad.addColorStop(1, '#00000000');
  ctx.fillStyle = grad;
  isoEllipse(ctx, 56, 30, 10, 8, '#ffffff');
  ctx.fill();

  g.add(spriteQuad(cvs, 88, 60, 0, 6, 0, 10));
  return g;
}

/** Futuristic command console: half-ellipse desk + big curved screen behind. Canvas 130x96. */
export function buildCommandConsole(accent: number): THREE.Group {
  const g = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 130; cvs.height = 96;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const accentCss = css(accent);

  ctx.fillStyle = '#00000055';
  ctx.beginPath(); ctx.ellipse(65, 92, 34, 5, 0, 0, Math.PI * 2); ctx.fill();

  // Console base: half-ellipse
  ctx.fillStyle = '#14141c';
  ctx.beginPath();
  ctx.ellipse(65, 80, 44, 14, 0, Math.PI, 2 * Math.PI);
  ctx.fill();
  ctx.fillStyle = '#1e1e2a';
  ctx.beginPath();
  ctx.ellipse(65, 82, 38, 10, 0, Math.PI, 2 * Math.PI);
  ctx.fill();

  // Top glow strip
  ctx.fillStyle = accentCss;
  ctx.fillRect(30, 70, 70, 4);

  // Big screen behind console
  ctx.fillStyle = '#040d1a';
  ctx.fillRect(32, 28, 66, 36);
  ctx.strokeStyle = accentCss;
  ctx.lineWidth = 2;
  ctx.strokeRect(32, 28, 66, 36);
  drawChart(ctx, 36, 36, 58, 24, '#3aa5ff');

  // Screen top border accent
  ctx.fillStyle = accentCss;
  ctx.fillRect(30, 24, 70, 4);

  g.add(spriteQuad(cvs, 86, 68, 0, 3, 0, 10));
  return g;
}

/** Office plant: pot + leafy blobs. Canvas 40x56. */
export function buildPlant(): THREE.Group {
  const g = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 40; cvs.height = 56;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#00000055';
  ctx.beginPath(); ctx.ellipse(20, 52, 8, 2, 0, 0, Math.PI * 2); ctx.fill();

  // Pot
  isoBox(ctx, 20, 48, 24, 14, 12, '#6b3020', '#4a2218', '#381a10');

  // Leaves stacked
  const leaf = '#1d7a3a';
  isoEllipse(ctx, 20, 40, 14, 8, leaf);
  isoEllipse(ctx, 20, 32, 10, 7, leaf);
  isoEllipse(ctx, 20, 26, 6, 5, leaf);

  g.add(spriteQuad(cvs, 28, 36, 0, 2, 0, 10));
  return g;
}

/** VIP leather sofa with golden trim. Canvas 100x60. */
export function buildSofa(): THREE.Group {
  const g = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 100; cvs.height = 60;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#00000055';
  ctx.beginPath(); ctx.ellipse(50, 56, 22, 3, 0, 0, Math.PI * 2); ctx.fill();

  // Seat
  isoBox(ctx, 50, 48, 64, 28, 10, '#4a2e1a', '#352014', '#281710');

  // Backrest
  isoBox(ctx, 50, 32, 64, 8, 14, '#382414', '#281710', '#1e100a');

  // Gold trim line
  ctx.strokeStyle = '#ffb700';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(20, 36); ctx.lineTo(80, 36); ctx.stroke();

  g.add(spriteQuad(cvs, 70, 44, 0, 2, 0, 10));
  return g;
}

/** Giant video wall (back wall full of screens). Canvas (len x 56). */
export function buildVideoWall(variant: 'green' | 'blue' | 'purple' = 'blue',
  accent: number, lenUnits: number): THREE.Group {
  const g = new THREE.Group();
  const canvasW = Math.max(150, Math.round(lenUnits * 1.4));
  const canvasH = 56;
  const cvs = document.createElement('canvas');
  cvs.width = canvasW; cvs.height = canvasH;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const accentCss = css(accent);
  const screenW = (canvasW - 24) / 3;
  const screenH = 32;
  const screenY = 14;

  // Base panel
  ctx.fillStyle = '#0d0d12';
  ctx.fillRect(0, 34, canvasW, 20);
  ctx.strokeStyle = '#1a1a2e';
  ctx.lineWidth = 1;
  ctx.strokeRect(1, 35, canvasW - 2, 18);

  // Accent underline
  ctx.fillStyle = accentCss;
  ctx.fillRect(0, 30, canvasW, 4);

  // Three screens
  for (let i = 0; i < 3; i++) {
    const sx = 12 + i * (screenW + 6);
    ctx.fillStyle = '#040d1a';
    ctx.fillRect(sx, screenY, screenW, screenH);
    ctx.strokeStyle = accentCss;
    ctx.lineWidth = 1;
    ctx.strokeRect(sx, screenY, screenW, screenH);
    drawChart(ctx, sx + 2, screenY + 3, screenW - 4, screenH - 6,
      variant === 'green' ? '#00ff88' :
        variant === 'blue' ? '#3aa5ff' : '#aa66ff');
  }

  const worldH = canvasH / canvasW * lenUnits * 0.6;
  g.add(spriteQuad(cvs, lenUnits, worldH, 0, 2, 0, 10));
  return g;
}

/** Zone wall segment: dark panel + accent top cap. Canvas (len x 44). */
export function buildZoneWall(accent: number, length: number): THREE.Group {
  const g = new THREE.Group();
  const canvasW = Math.max(80, Math.round(length * 1.4));
  const canvasH = 44;
  const cvs = document.createElement('canvas');
  cvs.width = canvasW; cvs.height = canvasH;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#14141c';
  ctx.fillRect(0, 14, canvasW, 28);
  ctx.strokeStyle = '#1e1e2a';
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 14, canvasW, 28);

  ctx.fillStyle = css(accent);
  ctx.fillRect(0, 8, canvasW, 6);

  // side posts
  ctx.fillStyle = '#101014';
  ctx.fillRect(0, 10, 6, 34);
  ctx.fillRect(canvasW - 6, 10, 6, 34);

  const worldH = canvasH / canvasW * length * 0.6;
  g.add(spriteQuad(cvs, length, worldH, 0, 2, 0, 10));
  return g;
}

/** Chief podium holographic rings (animated externally). Returns ring meshes. */
export function buildHoloRings(): {
  group: THREE.Group; ring1: THREE.Mesh; ring2: THREE.Mesh; ring3: THREE.Mesh;
} {
  const group = new THREE.Group();

  const goldMat = new THREE.MeshBasicMaterial({ color: 0xffcc00, transparent: true, opacity: 0.9 });
  const cyanMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.7 });
  const purpleMat = new THREE.MeshBasicMaterial({ color: 0xbd00ff, transparent: true, opacity: 0.5 });

  const ring1 = new THREE.Mesh(new THREE.TorusGeometry(78, 2.5, 10, 40), goldMat);
  ring1.rotation.x = Math.PI / 2;
  ring1.position.y = 48;
  group.add(ring1);

  const ring2 = new THREE.Mesh(new THREE.TorusGeometry(98, 2, 10, 44), cyanMat);
  ring2.rotation.x = Math.PI / 2 + 0.15;
  ring2.position.y = 58;
  group.add(ring2);

  const ring3 = new THREE.Mesh(new THREE.TorusGeometry(118, 1.5, 10, 48), purpleMat);
  ring3.rotation.x = Math.PI / 2 - 0.1;
  ring3.position.y = 70;
  group.add(ring3);

  return { group, ring1, ring2, ring3 };
}

/** Knowledge-graph holo-net on the floor: glowing nodes + links. */
export function buildHoloNet(ctx: PropContext, originGx: number, originGy: number, accent: number): THREE.Group {
  const g = new THREE.Group();
  const gold = new THREE.MeshBasicMaterial({ color: accent });

  const nodes: Array<[number, number]> = [
    [4, 4], [8, 3], [11, 6], [6, 8], [9, 10], [3, 9],
  ];
  const world = nodes.map(([gx, gy]) => {
    const p = ctx.gridToWorld(originGx + gx, originGy + gy);
    return new THREE.Vector3(p.x, 5, p.z);
  });

  const links: Array<[number, number]> = [[0, 1], [1, 2], [0, 3], [3, 4], [4, 2], [3, 5], [0, 5], [1, 4]];
  const linkMat = new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.5 });
  for (const [a, b] of links) {
    const va = world[a]; const vb = world[b];
    const mid = va.clone().add(vb).multiplyScalar(0.5);
    const len = va.distanceTo(vb);
    const link = new THREE.Mesh(new THREE.BoxGeometry(len, 1.2, 1.2), linkMat);
    link.position.copy(mid);
    link.rotation.y = -Math.atan2(vb.z - va.z, vb.x - va.x);
    g.add(link);
  }

  world.forEach((p, i) => {
    const node = new THREE.Mesh(new THREE.SphereGeometry(i % 2 === 0 ? 5 : 3.5, 6, 5), gold);
    node.position.set(p.x, 5 + (i % 3) * 2, p.z);
    g.add(node);
  });

  return g;
}

/** Zone wall segment: dark panel + accent top cap. Canvas (len x 44). */
export function buildWallStrip(accent: number, length: number): THREE.Group {
  return buildZoneWall(accent, length);
}
