/** Builds all floor geometry */

import * as THREE from 'three';
import { createPlaceholderTexture } from '../utils/assets.js';
import {
  TILE_W, TILE_H, GRID_W, GRID_H, ZONE_SIZE, CORRIDOR_W,
  ZONES, CHIEF_CENTER, ENTRANCE, CORRIDOR_Y, SOUTH_SUPPORT_Y,
  ZoneKey,
} from '../data/floorConfig.js';
import { gridToScreen, getIsoRect } from '../utils/iso.js';

export interface FloorGeometryParts {
  zones: THREE.Group;
  chiefCenter: THREE.Group;
  chiefCenterMesh: THREE.Mesh;
  corridor: THREE.Group;
  corridorMesh: THREE.Mesh;
  entrance: THREE.Group;
  entranceMesh: THREE.Mesh;
  southSupport: THREE.Group;
  southSupportMesh: THREE.Mesh;
  zoneMeshes: Map<ZoneKey, THREE.Mesh>;
}

export class FloorBuilder {
  private zoneTextures: Map<ZoneKey, THREE.Texture> = new Map();
  private chiefTexture: THREE.Texture;
  private corridorTexture: THREE.Texture;
  private entranceTexture: THREE.Texture;
  private southTexture: THREE.Texture;

  constructor() {
    // Create placeholder textures (will be replaced by real assets)
    this.chiefTexture = this.createZoneTexture(0x0d0d12, 0x00d4aa);
    this.corridorTexture = this.createZoneTexture(0x0d0d12, 0x00d4aa);
    this.entranceTexture = this.createZoneTexture(0x1a1a2e, 0x2a2a3a);
    this.southTexture = this.createZoneTexture(0x0d0d12, 0x2a2a3a);

    // Zone textures
    Object.entries(ZONES).forEach(([key, zone]) => {
      this.zoneTextures.set(key as any, this.createZoneTexture(zone.color, zone.accent));
    });
  }

  private createZoneTexture(baseColor: number, accentColor: number): THREE.Texture {
    return createPlaceholderTexture(baseColor);
  }

  /** Convert grid coordinates to world coordinates (for Three.js) */
  public gridToScreen(gx: number, gy: number): { x: number; y: number } {
    return {
      x: (gx - gy) * (64 / 2), // TILE_W = 64
      y: (gx + gy) * (32 / 2), // TILE_H = 32
    };
  }

  /** Convert grid coordinates to world coordinates (Three.js: x, z) */
  public gridToWorld(gx: number, gy: number): { x: number; y: number; z: number } {
    const screen = this.gridToScreen(gx, gy);
    return { x: screen.x, y: 0, z: screen.y };
  }

  /** Build a single zone mesh */
  private buildZoneMesh(key: ZoneKey, zone: any, texture: THREE.Texture): THREE.Mesh {
    const px = zone.x * 64; // TILE_W
    const py = zone.y * 32; // TILE_H
    const zw = 16 * 64; // ZONE_SIZE * TILE_W
    const zh = 16 * 32; // ZONE_SIZE * TILE_H

    // Create geometry from isometric rectangle
    const corners = getIsoRect(px, py, zw, zh);
    const shape = new THREE.Shape();
    shape.moveTo(corners[0], corners[1]);
    shape.lineTo(corners[2], corners[3]);
    shape.lineTo(corners[4], corners[5]);
    shape.lineTo(corners[6], corners[7]);
    shape.lineTo(corners[0], corners[1]);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2); // Lay flat
    geometry.translate(0, 0.01, 0); // Slightly above ground to avoid z-fighting

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide,
      roughness: 0.9,
      metalness: 0.1,
      depthWrite: true,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = `zone_${key}`;
    mesh.userData = { zoneKey: key, type: 'zone' };
    mesh.receiveShadow = false;

    return mesh;
  }

  /** Build chief center podium */
  private buildChiefCenterMesh(texture: THREE.Texture): THREE.Mesh {
    const { x, y, size } = { x: 32, y: 22, size: 12 }; // CHIEF_CENTER
    const px = x * 64;
    const py = y * 32;
    const w = size * 64;
    const h = size * 32;

    const corners = getIsoRect(px, py, w, h);
    const shape = new THREE.Shape();
    shape.moveTo(corners[0], corners[1]);
    shape.lineTo(corners[2], corners[3]);
    shape.lineTo(corners[4], corners[5]);
    shape.lineTo(corners[6], corners[7]);
    shape.lineTo(corners[0], corners[1]);

    // Extrude for podium height
    const extrudeSettings = {
      depth: 8, // Podium height
      bevelEnabled: true,
      bevelThickness: 2,
      bevelSize: 1.5,
      bevelSegments: 4,
    };

    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0, 0);

    // Two materials: base + accent rim
    const baseMaterial = new THREE.MeshStandardMaterial({
      color: 0x0d0d12,
      roughness: 0.3,
      metalness: 0.7,
      roughnessMap: null,
      metalnessMap: null,
    });

    const accentMaterial = new THREE.MeshStandardMaterial({
      color: 0x00d4aa,
      emissive: 0x00d4aa,
      emissiveIntensity: 0.2,
      roughness: 0.1,
      metalness: 0.9,
    });

    const mesh = new THREE.Mesh(geometry, [baseMaterial, accentMaterial]);
    mesh.name = 'chief_center';
    mesh.position.y = 0;
    mesh.castShadow = false;
    mesh.receiveShadow = false;

    return mesh;
  }

  /** Build main corridor */
  private buildCorridorMesh(texture: THREE.Texture): THREE.Mesh {
    const y = 24; // CORRIDOR_Y
    const px = 0;
    const py = y * 32;
    const w = 80 * 64; // GRID_W * TILE_W
    const h = 4 * 32; // CORRIDOR_W * TILE_H

    const corners = getIsoRect(px, py, w, h);
    const shape = new THREE.Shape();
    shape.moveTo(corners[0], corners[1]);
    shape.lineTo(corners[2], corners[3]);
    shape.lineTo(corners[4], corners[5]);
    shape.lineTo(corners[6], corners[7]);
    shape.lineTo(corners[0], corners[1]);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0.005, 0); // Slightly above zones

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      transparent: true,
      opacity: 0.7,
      side: THREE.DoubleSide,
      roughness: 0.8,
      metalness: 0.2,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = 'corridor';
    mesh.position.y = 0.005;
    mesh.receiveShadow = false;

    return mesh;
  }

  /** Build entrance */
  private buildEntranceMesh(texture: THREE.Texture): THREE.Mesh {
    const { x, y, w, h } = { x: 30, y: 0, w: 20, h: 6 }; // ENTRANCE
    const px = x * 64;
    const py = y * 32;
    const ww = w * 64;
    const hh = h * 32;

    const corners = getIsoRect(px, py, ww, hh);
    const shape = new THREE.Shape();
    shape.moveTo(corners[0], corners[1]);
    shape.lineTo(corners[2], corners[3]);
    shape.lineTo(corners[4], corners[5]);
    shape.lineTo(corners[6], corners[7]);
    shape.lineTo(corners[0], corners[1]);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0.002, 0);

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide,
      roughness: 0.9,
      metalness: 0.1,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = 'entrance';
    mesh.position.y = 0.002;

    return mesh;
  }

  /** Build south support area */
  private buildSouthSupportMesh(texture: THREE.Texture): THREE.Mesh {
    const y = 48; // SOUTH_SUPPORT_Y
    const px = 0;
    const py = y * 32;
    const w = 80 * 64;
    const h = (60 - y) * 32; // GRID_H - y

    const corners = getIsoRect(px, py, w, h);
    const shape = new THREE.Shape();
    shape.moveTo(corners[0], corners[1]);
    shape.lineTo(corners[2], corners[3]);
    shape.lineTo(corners[4], corners[5]);
    shape.lineTo(corners[6], corners[7]);
    shape.lineTo(corners[0], corners[1]);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0.001, 0);

    const material = new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide,
      roughness: 0.9,
      metalness: 0.1,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = 'south_support';
    mesh.position.y = 0.001;

    return mesh;
  }

  /** Build direction arrows on corridor */
  private buildCorridorArrows(): THREE.Group {
    const group = new THREE.Group();
    group.name = 'corridor_arrows';

    const y = 24; // CORRIDOR_Y
    const arrowMaterial = new THREE.MeshBasicMaterial({
      color: 0x00d4aa,
      transparent: true,
      opacity: 0.4,
      depthWrite: false,
    });

    for (let i = 0; i < 80; i += 4) { // GRID_W = 80
      const screen1 = this.gridToScreen(i, y + 1);
      const screen2 = this.gridToScreen(i, y + 3); // CORRIDOR_W - 1
      const midX = (screen1.x + screen2.x) / 2;
      const midY = (screen1.y + screen2.y) / 2;

      // Arrow geometry (simple triangle)
      const arrowGeo = new THREE.BufferGeometry();
      const vertices = new Float32Array([
        midX - 8, 0.01, midY,
        midX, 0.01, midY - 4,
        midX + 8, 0.01, midY,
        midX, 0.01, midY - 4,
        midX, 0.01, midY + 4,
      ]);
      arrowGeo.setAttribute('position', new THREE.BufferAttribute(vertices, 3));

      const arrow = new THREE.Mesh(
        new THREE.ShapeGeometry(new THREE.Shape()
          .moveTo(-8, 0)
          .lineTo(0, -4)
          .lineTo(8, 0)
          .lineTo(0, -4)
          .lineTo(0, 4)
        ),
        new THREE.MeshBasicMaterial({ color: 0x00d4aa, transparent: true, opacity: 0.4, depthWrite: false })
      );
      arrow.rotation.x = -Math.PI / 2;
      arrow.position.set(midX, 0.015, midY);
      group.add(arrow);
    }

    return group;
  }

  /** Build all floor parts */
  public buildAll(params: {
    zones: any;
    chiefCenter: any;
    entrance: any;
    corridorY: number;
    southSupportY: number;
    gridW: number;
    gridH: number;
    tileW: number;
    tileH: number;
    zoneSize: number;
    corridorW: number;
  }): FloorGeometryParts {
    const zoneMeshes = new Map();

    // Zones group
    const zonesGroup = new THREE.Group();
    zonesGroup.name = 'zones';

    const zones = params.zones;
    Object.entries(zones).forEach(([key, zone]: [string, any]) => {
      // Create a simple colored texture for each zone
      const canvas = document.createElement('canvas');
      canvas.width = 64; canvas.height = 64;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = `#${zone.color.toString(16).padStart(6, '0')}`;
      ctx.fillRect(0, 0, 64, 64);
      // Grid lines
      ctx.strokeStyle = '#ffffff11';
      ctx.lineWidth = 1;
      for (let i = 0; i < 64; i += 8) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 64); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(64, i); ctx.stroke();
      }
      const texture = new THREE.CanvasTexture(canvas);
      texture.magFilter = THREE.NearestFilter;
      texture.minFilter = THREE.LinearMipmapLinearFilter;
      texture.generateMipmaps = true;

      const mesh = this.buildZoneMesh(key as any, zone, texture);
      zonesGroup.add(mesh);
      zoneMeshes.set(key, mesh);
    })

    // Chief center
    const chiefCanvas = document.createElement('canvas');
    chiefCanvas.width = 64; chiefCanvas.height = 64;
    const chiefCtx = chiefCanvas.getContext('2d')!;
    chiefCtx.fillStyle = '#0d0d12'; chiefCtx.fillRect(0, 0, 64, 64);
    chiefCtx.strokeStyle = '#00d4aa'; chiefCtx.lineWidth = 2;
    chiefCtx.strokeRect(2, 2, 60, 60);
    const chiefTexture = new THREE.CanvasTexture(chiefCanvas);
    chiefTexture.magFilter = THREE.NearestFilter;
    chiefTexture.minFilter = THREE.LinearMipmapLinearFilter;
    chiefTexture.generateMipmaps = true;

    const chiefCenterMesh = this.buildChiefCenterMesh(chiefTexture);
    const chiefCenterGroup = new THREE.Group();
    chiefCenterGroup.name = 'chief_center';
    chiefCenterGroup.add(chiefCenterMesh);

    // Corridor
    const corridorCanvas = document.createElement('canvas');
    corridorCanvas.width = 64; corridorCanvas.height = 64;
    const corridorCtx = corridorCanvas.getContext('2d')!;
    corridorCtx.fillStyle = '#0d0d12'; corridorCtx.fillRect(0, 0, 64, 64);
    corridorCtx.strokeStyle = '#00d4aa'; corridorCtx.lineWidth = 1;
    for (let i = 0; i < 64; i += 8) {
      corridorCtx.beginPath(); corridorCtx.moveTo(i, 0); corridorCtx.lineTo(i, 64); corridorCtx.stroke();
      corridorCtx.beginPath(); corridorCtx.moveTo(0, i); corridorCtx.lineTo(64, i); corridorCtx.stroke();
    }
    const corridorTexture = new THREE.CanvasTexture(corridorCanvas);
    corridorTexture.magFilter = THREE.NearestFilter;
    corridorTexture.minFilter = THREE.LinearMipmapLinearFilter;
    corridorTexture.generateMipmaps = true;

    const corridorMesh = this.buildCorridorMesh(corridorTexture);
    const corridorGroup = new THREE.Group();
    corridorGroup.name = 'corridor';
    corridorGroup.add(corridorMesh);
    corridorGroup.add(this.buildCorridorArrows());

    // Entrance
    const entranceCanvas = document.createElement('canvas');
    entranceCanvas.width = 64; entranceCanvas.height = 64;
    const entranceCtx = entranceCanvas.getContext('2d')!;
    entranceCtx.fillStyle = '#1a1a2e'; entranceCtx.fillRect(0, 0, 64, 64);
    entranceCtx.strokeStyle = '#2a2a3a'; entranceCtx.lineWidth = 1;
    for (let i = 0; i < 64; i += 8) {
      entranceCtx.beginPath(); entranceCtx.moveTo(i, 0); entranceCtx.lineTo(i, 64); entranceCtx.stroke();
      entranceCtx.beginPath(); entranceCtx.moveTo(0, i); entranceCtx.lineTo(64, i); entranceCtx.stroke();
    }
    const entranceTexture = new THREE.CanvasTexture(entranceCanvas);
    entranceTexture.magFilter = THREE.NearestFilter;
    entranceTexture.minFilter = THREE.LinearMipmapLinearFilter;
    entranceTexture.generateMipmaps = true;

    const entranceMesh = this.buildEntranceMesh(entranceTexture);
    const entranceGroup = new THREE.Group();
    entranceGroup.name = 'entrance';
    entranceGroup.add(entranceMesh);

    // South support
    const southCanvas = document.createElement('canvas');
    southCanvas.width = 64; southCanvas.height = 64;
    const southCtx = southCanvas.getContext('2d')!;
    southCtx.fillStyle = '#0d0d12'; southCtx.fillRect(0, 0, 64, 64);
    southCtx.strokeStyle = '#2a2a3a'; southCtx.lineWidth = 1;
    for (let i = 0; i < 64; i += 8) {
      southCtx.beginPath(); southCtx.moveTo(i, 0); southCtx.lineTo(i, 64); southCtx.stroke();
      southCtx.beginPath(); southCtx.moveTo(0, i); southCtx.lineTo(64, i); southCtx.stroke();
    }
    const southTexture = new THREE.CanvasTexture(southCanvas);
    southTexture.magFilter = THREE.NearestFilter;
    southTexture.minFilter = THREE.LinearMipmapLinearFilter;
    southTexture.generateMipmaps = true;

    const southSupportMesh = this.buildSouthSupportMesh(southTexture);
    const southSupportGroup = new THREE.Group();
    southSupportGroup.name = 'south_support';
    southSupportGroup.add(southSupportMesh);

    return {
      zones: zonesGroup,
      chiefCenter: chiefCenterGroup,
      chiefCenterMesh: chiefCenterGroup.children[0] as THREE.Mesh,
      corridor: corridorGroup,
      corridorMesh: corridorGroup.children[0] as THREE.Mesh,
      entrance: entranceGroup,
      entranceMesh: entranceGroup.children[0] as THREE.Mesh,
      southSupport: southSupportGroup,
      southSupportMesh: southSupportGroup.children[0] as THREE.Mesh,
      zoneMeshes,
    };
  }
}