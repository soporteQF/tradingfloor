/** Builds all floor geometry */

import * as THREE from 'three';
import { createPlaceholderTexture } from '../utils/assets.js';
import { css, createHabboTileTexture } from '../utils/pixelArt.js';
import {
  buildDesk,
  buildServerRack,
  buildHoloDome,
  buildCommandConsole,
  buildPlant,
  buildSofa,
  buildVideoWall,
  buildHoloNet,
  buildHoloRings,
  buildZoneWall,
} from './PropsBuilder.js';
import {
  TILE_W, TILE_H, GRID_W, GRID_H, ZONE_SIZE, CORRIDOR_W,
  ZONES, CHIEF_CENTER, ENTRANCE, CORRIDOR_Y, SOUTH_SUPPORT_Y,
  CHIEF_POS, ZoneKey,
} from '../data/floorConfig.js';
import { gridToScreen, getIsoRect } from '../utils/iso.js';

export interface FloorGeometryParts {
  zones: THREE.Group;
  chiefCenter: THREE.Group;
  chiefCenterMesh: THREE.Mesh;
  corridor: THREE.Group;
  corridorGroup: THREE.Group;
  corridorMesh: THREE.Mesh;
  entrance: THREE.Group;
  entranceGroup: THREE.Group;
  entranceMesh: THREE.Mesh;
  southSupport: THREE.Group;
  southSupportGroup: THREE.Group;
  southSupportMesh: THREE.Mesh;
  zoneMeshes: Map<ZoneKey, THREE.Mesh>;
  props: THREE.Group;
  holoRings: { group: THREE.Group; ring1: THREE.Mesh; ring2: THREE.Mesh; ring3: THREE.Mesh } | null;
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

  /** Build an isometric shape from getIsoRect corners, lying flat on XZ with UP normals.
   *  Shape-space Y is NEGATED so that after rotateX(-PI/2) (Y -> -Z) world Z = +screenY,
   *  matching avatars/lights/camera coordinates. */
  private isoShape(corners: number[]): THREE.Shape {
    const s = new THREE.Shape();
    s.moveTo(corners[0], -corners[1]);
    s.lineTo(corners[2], -corners[3]);
    s.lineTo(corners[4], -corners[5]);
    s.lineTo(corners[6], -corners[7]);
    s.lineTo(corners[0], -corners[1]);
    return s;
  }

  /** Build a single zone mesh */
  private buildZoneMesh(key: ZoneKey, zone: any, texture: THREE.Texture): THREE.Mesh {
    const px = zone.x * 64; // TILE_W
    const py = zone.y * 32; // TILE_H
    const zw = 16 * 64; // ZONE_SIZE * TILE_W
    const zh = 16 * 32; // ZONE_SIZE * TILE_H

    // Create geometry from isometric rectangle
    const corners = getIsoRect(px, py, zw, zh);
    const shape = this.isoShape(corners);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2); // Lay flat
    geometry.translate(0, 0.01, 0); // Slightly above ground to avoid z-fighting

    // Unlit material - bright like Habbo floor tiles
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      color: 0xffffff,
      side: THREE.DoubleSide,
      depthWrite: true,
      transparent: false,
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
    const shape = this.isoShape(corners);

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
      color: 0x00e5ff,
      emissive: 0x00e5ff,
      emissiveIntensity: 0.35,
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
    const shape = this.isoShape(corners);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0.005, 0); // Slightly above zones

    const material = new THREE.MeshBasicMaterial({
      map: texture,
      color: 0xffffff,
      side: THREE.DoubleSide,
      transparent: false,
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
    const shape = this.isoShape(corners);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0.002, 0);

    const material = new THREE.MeshBasicMaterial({
      map: texture,
      color: 0xffffff,
      side: THREE.DoubleSide,
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
    const shape = this.isoShape(corners);

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, 0.001, 0);

    const material = new THREE.MeshBasicMaterial({
      map: texture,
      color: 0xffffff,
      side: THREE.DoubleSide,
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
    const zoneMeshes = new Map<ZoneKey, THREE.Mesh>();

    // Zones group with Habbo tile textures per zone
    const zonesGroup = new THREE.Group();
    zonesGroup.name = 'zones';

    const zones = params.zones;
    Object.entries(zones).forEach(([key, zone]: [string, any]) => {
      const texCanvas = createHabboTileTexture(
        zone.color,
        zone.color ^ 0x222222,
        '#ffffff22', '#00000044'
      );
      const texture = new THREE.CanvasTexture(texCanvas);
      texture.magFilter = THREE.NearestFilter;
      texture.minFilter = THREE.NearestFilter;

      const mesh = this.buildZoneMesh(key as ZoneKey, zone, texture);
      mesh.receiveShadow = false;
      zonesGroup.add(mesh);
      zoneMeshes.set(key as ZoneKey, mesh);
    });

    // Props + walls group
    const propsGroup = new THREE.Group();
    propsGroup.name = 'props';

    /** Place a sprite prop at world grid coords. */
    const placeProp = (kind: string, gx: number, gy: number, variant?: string): void => {
      const pos = this.gridToWorld(gx, gy);
      let obj: THREE.Group | THREE.Mesh;
      switch (kind) {
        case 'desk': obj = buildDesk(variant as any, 2); break;
        case 'rack': obj = buildServerRack('blue'); break;
        case 'plant': obj = buildPlant(); break;
        case 'sofa': obj = buildSofa(); break;
        case 'console': obj = buildCommandConsole(0x00e5ff); break;
        case 'dome': obj = buildHoloDome(0xe052ff); break;
        default: return;
      }
      // Offset so it sits centered on the grid cell, floating slightly
      obj.position.set(pos.x, 4, pos.z);
      obj.renderOrder = Math.round(pos.z / 8) + 20;
      propsGroup.add(obj);
    };

    const placeWall = (gx: number, gy: number, accent: number, rotY = 0): void => {
      const pos = this.gridToWorld(gx, gy);
      const wall = buildZoneWall(accent, 18);
      wall.position.set(pos.x, 2, pos.z);
      wall.rotation.y = rotY;
      wall.renderOrder = Math.round(pos.z / 8) + 30;
      propsGroup.add(wall);
    };

    // Per-zone prop plans (local coords within the 16x16 zone)
    const zonePlans: Record<string, Array<{ kind: string; lx: number; ly: number; variant?: string }>> = {
      research: [
        { kind: 'console', lx: 8, ly: 8 },
        { kind: 'desk', lx: 4, ly: 12, variant: 'blue' },
        { kind: 'desk', lx: 12, ly: 12, variant: 'blue' },
        { kind: 'plant', lx: 4, ly: 4 },
        { kind: 'plant', lx: 12, ly: 4 },
      ],
      validation: [
        { kind: 'desk', lx: 6, ly: 10, variant: 'green' },
        { kind: 'desk', lx: 10, ly: 10, variant: 'green' },
        { kind: 'desk', lx: 6, ly: 4, variant: 'green' },
        { kind: 'desk', lx: 10, ly: 4, variant: 'green' },
        { kind: 'plant', lx: 2, ly: 14 },
      ],
      execution: [
        { kind: 'desk', lx: 6, ly: 10, variant: 'green' },
        { kind: 'desk', lx: 10, ly: 10, variant: 'green' },
        { kind: 'desk', lx: 14, ly: 10, variant: 'green' },
        { kind: 'desk', lx: 4, ly: 14, variant: 'green' },
        { kind: 'desk', lx: 12, ly: 14, variant: 'green' },
        { kind: 'plant', lx: 8, ly: 4 },
      ],
      guardian: [
        { kind: 'sofa', lx: 8, ly: 8 },
        { kind: 'plant', lx: 12, ly: 12 },
        { kind: 'plant', lx: 4, ly: 4 },
      ],
      regime: [
        { kind: 'dome', lx: 8, ly: 8 },
        { kind: 'plant', lx: 4, ly: 4 },
        { kind: 'plant', lx: 12, ly: 4 },
      ],
      alpha: [
        { kind: 'rack', lx: 4, ly: 8 },
        { kind: 'rack', lx: 12, ly: 8 },
        { kind: 'rack', lx: 4, ly: 12 },
        { kind: 'rack', lx: 12, ly: 12 },
        { kind: 'plant', lx: 8, ly: 4 },
      ],
    };

    // Place props inside each zone
    Object.entries(ZONES).forEach(([key, zone]) => {
      const plan = zonePlans[key] ?? [];
      plan.forEach(p => {
        placeProp(p.kind, zone.x + p.lx, zone.y + p.ly, p.variant);
      });

      // Zone walls around the perimeter (just outside the zone)
      const zx = zone.x; const zy = zone.y;
      const accent = zone.accent;
      placeWall(zx + 8, zy - 1, accent, 0);
      placeWall(zx + 8, zy + 17, accent, 0);
      placeWall(zx - 1, zy + 8, accent, Math.PI / 2);
      placeWall(zx + 17, zy + 8, accent, Math.PI / 2);

      // Video wall along the South edge of each zone
      const vw = buildVideoWall('blue' as any, accent, 14);
      const vwPos = this.gridToWorld(zx + 8, zy - 1);
      vw.position.set(vwPos.x, 2, vwPos.z);
      vw.rotation.y = 0;
      vw.renderOrder = Math.round(vwPos.z / 8) + 35;
      propsGroup.add(vw);
    });

    // Chief center
    const chiefCenterMesh = this.buildChiefCenterMesh(createPlaceholderTexture(0x0d0d12));
    const chiefCenterGroup = new THREE.Group();
    chiefCenterGroup.name = 'chief_center';
    chiefCenterGroup.add(chiefCenterMesh);

    // Holographic rings above the Chief podium
    const chiefWorld = this.gridToWorld(CHIEF_POS.x, CHIEF_POS.y);
    const holoRings = buildHoloRings();
    holoRings.group.position.set(chiefWorld.x, 0, chiefWorld.z);
    holoRings.group.renderOrder = 40;
    propsGroup.add(holoRings.group);

    // Knowledge-graph holo-net across the alpha zone floor
    const holoNet = buildHoloNet({
      gridToWorld: this.gridToWorld.bind(this),
    }, ZONES.alpha.x, ZONES.alpha.y, ZONES.alpha.accent);
    holoNet.traverse(child => {
      if (child instanceof THREE.Mesh) { child.renderOrder = 15; }
    });
    propsGroup.add(holoNet);

    // Corridor / entrance / south support with tech floor texture
    const corridorGroup = new THREE.Group();
    corridorGroup.name = 'corridor';
    const corridorMesh = this.buildCorridorMesh(createPlaceholderTexture(0x0d0d12));
    corridorGroup.add(corridorMesh);
    corridorGroup.add(this.buildCorridorArrows());

    const entranceGroup = new THREE.Group();
    entranceGroup.name = 'entrance';
    const entranceMesh = this.buildEntranceMesh(createPlaceholderTexture(0x1a1a2e));
    entranceGroup.add(entranceMesh);

    const southSupportGroup = new THREE.Group();
    southSupportGroup.name = 'south_support';
    const southSupportMesh = this.buildSouthSupportMesh(createPlaceholderTexture(0x0d0d12));
    southSupportGroup.add(southSupportMesh);

    return {
      zones: zonesGroup,
      chiefCenter: chiefCenterGroup,
      chiefCenterMesh: chiefCenterMesh,
      corridor: corridorGroup,
      corridorGroup: corridorGroup,
      corridorMesh: corridorMesh,
      entrance: entranceGroup,
      entranceGroup: entranceGroup,
      entranceMesh: entranceMesh,
      southSupport: southSupportGroup,
      southSupportGroup: southSupportGroup,
      southSupportMesh: southSupportMesh,
      zoneMeshes,
      props: propsGroup,
      holoRings: holoRings,
    };
  }
}