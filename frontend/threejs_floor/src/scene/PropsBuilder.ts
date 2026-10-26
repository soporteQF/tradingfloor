/** Habbo-style Props - pixel art sprites as flat quads */

import * as THREE from 'three';

/** Build a flat sprite quad lying on the floor plane */
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

/** Trading desk with monitors - Habbo style */
export function buildDesk(variant: 'green' | 'blue' | 'purple' = 'green'): THREE.Group {
  const dg = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 128; cvs.height = 96;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const colors = {
    green: { desk: '#2d4a2d', screen: '#00ff88', frame: '#1a3a1a' },
    blue:  { desk: '#1a2a4a', screen: '#4488ff', frame: '#1a1a3a' },
    purple:{ desk: '#3a1a4a', screen: '#aa66ff', frame: '#2a1a3a' },
  }[variant];

  ctx.fillStyle = '#00000044';
  ctx.beginPath(); ctx.ellipse(64, 84, 28, 5, 0, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = colors.desk;
  ctx.beginPath();
  ctx.moveTo(64, 28);
  ctx.lineTo(100, 44);
  ctx.lineTo(64, 60);
  ctx.lineTo(28, 44);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#1a2a1a';
  ctx.beginPath();
  ctx.moveTo(28, 44);
  ctx.lineTo(28, 76);
  ctx.lineTo(100, 92);
  ctx.lineTo(100, 60);
  ctx.closePath();
  ctx.fill();

  const screenColor = variant === 'green' ? '#00ff88' : variant === 'blue' ? '#4488ff' : '#aa66ff';
  for (let i = 0; i < 2; i++) {
    const mx = [44, 84][i];
    ctx.fillStyle = '#1a1a2a';
    ctx.beginPath();
    ctx.moveTo(mx - 14, 20);
    ctx.lineTo(mx + 14, 28);
    ctx.lineTo(mx + 14, 52);
    ctx.lineTo(mx - 14, 44);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#0a1a0a';
    ctx.fillRect(mx - 11, 24, 22, 22);
    ctx.strokeStyle = variant === 'green' ? '#00ff88' : variant === 'blue' ? '#4488ff' : '#aa66ff';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(mx - 9, 38);
    ctx.lineTo(mx - 5, 32);
    ctx.lineTo(mx, 35);
    ctx.lineTo(mx + 5, 30);
    ctx.lineTo(mx + 9, 26);
    ctx.stroke();
  }

  ctx.fillStyle = '#1a2a1a';
  ctx.beginPath();
  ctx.moveTo(44, 76);
  ctx.lineTo(84, 92);
  ctx.lineTo(84, 108);
  ctx.lineTo(44, 92);
  ctx.closePath();
  ctx.fill();

  const dg2 = new THREE.Group();
  dg2.add(spriteQuad(cvs, 80, 72, 0, 4, 0, 10));
  return dg2;
}

/** Server rack */
export function buildServerRack(): THREE.Group {
  const rg = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 64; cvs.height = 128;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#00000044';
  ctx.beginPath(); ctx.ellipse(32, 116, 14, 3, 0, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#1a1a1a';
  ctx.beginPath();
  ctx.moveTo(10, 12);
  ctx.lineTo(54, 20);
  ctx.lineTo(54, 116);
  ctx.lineTo(10, 108);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#141414';
  ctx.beginPath();
  ctx.moveTo(54, 20);
  ctx.lineTo(54, 116);
  ctx.lineTo(64, 108);
  ctx.lineTo(64, 20);
  ctx.closePath();
  ctx.fill();

  for (let row = 0; row < 12; row++) {
    for (let col = 0; col < 3; col++) {
      if (Math.random() > 0.3) {
        ctx.fillStyle = Math.random() > 0.5 ? '#00ff88' : '#ffaa00';
        ctx.fillRect(56 + col * 3, 24 + row * 8, 2, 2);
      }
    }
  }

  ctx.strokeStyle = '#333333';
  ctx.lineWidth = 1;
  for (let y = 20; y < 116; y += 8) {
    ctx.beginPath();
    ctx.moveTo(12, y);
    ctx.lineTo(52, y + 8);
    ctx.stroke();
  }

  const rg2 = new THREE.Group();
  rg2.add(spriteQuad(cvs, 48, 96, 0, 4, 0, 10));
  return rg2;
}

/** Holographic dome */
export function buildHoloDome(accent: number): THREE.Group {
  const dg = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 128; cvs.height = 96;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const accentCss = `#${accent.toString(16).padStart(6, '0')}`;

  ctx.fillStyle = '#00000044';
  ctx.beginPath(); ctx.ellipse(64, 84, 30, 4, 0, 0, Math.PI * 2); ctx.fill();

  ctx.strokeStyle = '#333333';
  ctx.lineWidth = 3;
  ctx.beginPath(); ctx.ellipse(64, 70, 36, 12, 0, 0, Math.PI * 2); ctx.stroke();

  ctx.strokeStyle = `#${accent.toString(16).padStart(6, '0')}`;
  ctx.lineWidth = 1.5;
  ctx.globalAlpha = 0.6;
  for (let r = 8; r <= 36; r += 10) {
    ctx.beginPath(); ctx.ellipse(64, 38, r, r * 0.5, 0, 0, Math.PI); ctx.stroke();
  }
  for (let a = 0; a < 5; a++) {
    const ang = (a / 5) * Math.PI;
    const rx = 36 * Math.cos(ang);
    ctx.beginPath();
    ctx.moveTo(64 + rx, 38);
    ctx.bezierCurveTo(64 + rx * 0.3, 38 - 20, 64 - rx * 0.3, 38 - 20, 64 - rx, 38);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  const grad = ctx.createRadialGradient(64, 38, 0, 64, 38, 12);
  grad.addColorStop(0, `#${accent.toString(16).padStart(6, '0')}`);
  grad.addColorStop(1, '#00000000');
  ctx.fillStyle = grad;
  ctx.beginPath(); ctx.ellipse(64, 38, 12, 6, 0, 0, Math.PI * 2); ctx.fill();

  const dg2 = new THREE.Group();
  dg2.add(spriteQuad(cvs, 96, 72, 0, 6, 0, 10));
  return dg2;
}

/** Command console */
export function buildCommandConsole(accent: number): THREE.Group {
  const cg = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 144; cvs.height = 104;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  const accentCss = `#${accent.toString(16).padStart(6, '0')}`;

  ctx.fillStyle = '#00000044';
  ctx.beginPath(); ctx.ellipse(72, 96, 38, 5, 0, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#1a1a2a';
  ctx.beginPath();
  ctx.ellipse(72, 76, 50, 16, 0, Math.PI, 2 * Math.PI);
  ctx.fill();

  ctx.fillStyle = `#${accent.toString(16).padStart(6, '0')}`;
  ctx.fillRect(32, 64, 80, 4);

  ctx.fillStyle = '#0a0a1a';
  ctx.fillRect(28, 24, 88, 44);
  ctx.strokeStyle = `#${accent.toString(16).padStart(6, '0')}`;
  ctx.lineWidth = 2;
  ctx.strokeRect(28, 24, 88, 44);

  ctx.strokeStyle = '#00ff88';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(32, 52);
  ctx.lineTo(44, 40);
  ctx.lineTo(56, 44);
  ctx.lineTo(68, 34);
  ctx.lineTo(80, 42);
  ctx.lineTo(92, 30);
  ctx.lineTo(104, 38);
  ctx.stroke();

  ctx.fillStyle = `#${accent.toString(16).padStart(6, '0')}`;
  ctx.fillRect(28, 20, 88, 4);

  const cg2 = new THREE.Group();
  cg2.add(spriteQuad(cvs, 100, 72, 0, 3, 0, 10));
  return cg2;
}

/** Plant */
export function buildPlant(): THREE.Group {
  const pg = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 48; cvs.height = 64;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#00000044';
  ctx.beginPath(); ctx.ellipse(24, 56, 10, 2, 0, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#8b4513';
  ctx.beginPath();
  ctx.moveTo(10, 48);
  ctx.lineTo(38, 52);
  ctx.lineTo(38, 60);
  ctx.lineTo(10, 56);
  ctx.closePath();
  ctx.fill();

  const leaf = '#2d7a2d';
  ctx.fillStyle = leaf;
  ctx.beginPath(); ctx.ellipse(24, 40, 18, 10, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(24, 32, 14, 8, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(24, 26, 10, 6, 0, 0, Math.PI * 2); ctx.fill();

  const pg2 = new THREE.Group();
  pg2.add(spriteQuad(cvs, 32, 48, 0, 2, 0, 10));
  return pg2;
}

/** VIP Sofa */
export function buildSofa(): THREE.Group {
  const sg = new THREE.Group();
  const cvs = document.createElement('canvas');
  cvs.width = 120; cvs.height = 72;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#00000044';
  ctx.beginPath(); ctx.ellipse(60, 66, 28, 4, 0, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#4a2c1a';
  ctx.beginPath();
  ctx.moveTo(10, 44);
  ctx.lineTo(110, 48);
  ctx.lineTo(110, 68);
  ctx.lineTo(10, 64);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#3a2414';
  ctx.beginPath();
  ctx.moveTo(10, 24);
  ctx.lineTo(110, 28);
  ctx.lineTo(110, 48);
  ctx.lineTo(10, 44);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = '#ffd700';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(10, 28); ctx.lineTo(110, 32); ctx.stroke();

  const sg2 = new THREE.Group();
  sg2.add(spriteQuad(cvs, 80, 56, 0, 2, 0, 10));
  return sg2;
}

/** Video wall */
export function buildVideoWall(variant: 'green' | 'blue' | 'purple', accent: number, lenUnits: number): THREE.Group {
  const vg = new THREE.Group();
  const canvasW = 180;
  const canvasH = 56;
  const cvs = document.createElement('canvas');
  cvs.width = canvasW; cvs.height = canvasH;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#0a0a12';
  ctx.fillRect(0, 32, 180, 24);
  ctx.strokeStyle = '#1a1a2e';
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 32, 180, 24);

  const accentCss = `#${accent.toString(16).padStart(6, '0')}`;
  ctx.fillStyle = accentCss;
  ctx.fillRect(0, 28, 180, 4);

  const screenColors = { green: '#00ff88', blue: '#4488ff', purple: '#aa66ff' };
  const screenColor = screenColors[variant];
  for (let i = 0; i < 3; i++) {
    const sx = 10 + i * 56;
    ctx.fillStyle = '#0a1a1a';
    ctx.fillRect(sx, 4, 50, 24);
    ctx.strokeStyle = `#${accent.toString(16).padStart(6, '0')}`;
    ctx.lineWidth = 1;
    ctx.strokeRect(sx, 4, 50, 24);
    ctx.strokeStyle = { green: '#00ff88', blue: '#4488ff', purple: '#aa66ff' }[variant];
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(sx + 2, 24);
    ctx.lineTo(sx + 12, 16);
    ctx.lineTo(sx + 22, 18);
    ctx.lineTo(sx + 22, 10);
    ctx.lineTo(sx + 22, 10);
    ctx.lineTo(sx + 32, 18);
    ctx.lineTo(sx + 38, 14);
    ctx.stroke();
  }

  const vg2 = new THREE.Group();
  vg2.add(spriteQuad(cvs, lenUnits, 56 / 180 * lenUnits * 0.7, 0, 2, 0, 10));
  return vg2;
}

/** Zone wall */
export function buildZoneWall(accent: number, length: number): THREE.Group {
  const wg = new THREE.Group();
  const canvasW = Math.max(80, Math.round(length * 1.5));
  const canvasH = 48;
  const cvs = document.createElement('canvas');
  cvs.width = canvasW; cvs.height = canvasH;
  const ctx = cvs.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  ctx.fillStyle = '#1a1a1a';
  ctx.fillRect(0, 10, canvasW, 36);
  ctx.strokeStyle = '#2a2a2a';
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 10, canvasW, 36);

  ctx.fillStyle = `#${accent.toString(16).padStart(6, '0')}`;
  ctx.fillRect(0, 6, canvasW, 4);

  ctx.fillStyle = '#101010';
  ctx.fillRect(0, 6, 4, 40);
  ctx.fillRect(canvasW - 4, 6, 4, 40);

  const wg2 = new THREE.Group();
  wg2.add(spriteQuad(cvs, length, 48 / canvasW * length * 0.6, 0, 2, 0, 10));
  return wg2;
}

/** Chief holographic rings */
export function buildHoloRings(): {
  group: THREE.Group; ring1: THREE.Mesh; ring2: THREE.Mesh; ring3: THREE.Mesh;
} {
  const rg = new THREE.Group();

  const goldMat = new THREE.MeshBasicMaterial({ color: 0xffd700, transparent: true, opacity: 0.9, side: THREE.DoubleSide });
  const cyanMat = new THREE.MeshBasicMaterial({ color: 0x00ffff, transparent: true, opacity: 0.7, side: THREE.DoubleSide });
  const purpleMat = new THREE.MeshBasicMaterial({ color: 0xbd00ff, transparent: true, opacity: 0.5, side: THREE.DoubleSide });

  const ring1 = new THREE.Mesh(new THREE.RingGeometry(70, 74, 40), goldMat);
  ring1.rotation.x = Math.PI / 2;
  ring1.position.y = 48;
  rg.add(ring1);

  const ring2 = new THREE.Mesh(new THREE.RingGeometry(88, 92, 44), cyanMat);
  ring2.rotation.x = Math.PI / 2 + 0.15;
  ring2.position.y = 58;
  rg.add(ring2);

  const ring3 = new THREE.Mesh(new THREE.RingGeometry(106, 110, 48), purpleMat);
  ring3.rotation.x = Math.PI / 2 - 0.1;
  ring3.position.y = 68;
  rg.add(ring3);

  return { group: rg, ring1, ring2, ring3 };
}

/** Holo net */
export function buildHoloNet(ctx: any, originGx: number, originGy: number, accent: number): THREE.Group {
  const ng = new THREE.Group();
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
    ng.add(link);
  }

  world.forEach((p, i) => {
    const node = new THREE.Mesh(new THREE.SphereGeometry(i % 2 === 0 ? 5 : 3.5, 6, 5), gold);
    node.position.set(p.x, 5 + (i % 3) * 2, p.z);
    ng.add(node);
  });

  return ng;
}