/** Main Three.js scene - Habbo Hotel style */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { FloorBuilder } from './FloorBuilder.js';
import { AvatarSystem } from './AvatarSystem.js';
import { CameraController } from './CameraController.js';
import { gridToScreen } from '../utils/iso.js';
import { getApiClient } from '../net/ApiClient.js';
import {
  TILE_W, TILE_H, GRID_W, GRID_H, ZONE_SIZE, CORRIDOR_W,
  ZONES, CHIEF_CENTER, ENTRANCE, CORRIDOR_Y, SOUTH_SUPPORT_Y,
  OPERATOR_START, CHIEF_POS, ZONE_KEYS,
  CAMERA_DEFAULTS, CAMERA_FRUSTUM, REDUCED_MOTION_DEFAULTS,
  ZoneKey,
} from '../data/floorConfig.js';
import type { ChiefStatus, PaperStrategy } from '../net/ApiClient.js';

export interface FloorSceneOptions {
  canvas: HTMLCanvasElement;
  onStatusUpdate?: (status: ChiefStatus) => void;
  onError?: (error: Error) => void;
  reducedMotion?: boolean;
}

export class FloorScene {
  private renderer: THREE.WebGLRenderer;
  private scene: THREE.Scene;
  private camera: THREE.OrthographicCamera;
  private composer: EffectComposer;
  private floorBuilder: FloorBuilder;
  private avatarSystem: AvatarSystem;
  private cameraController: CameraController;

  private floorContainer: THREE.Group;
  private zoneMeshes: Map<ZoneKey, THREE.Mesh> = new Map();
  private chiefCenterMesh: THREE.Mesh | null = null;
  private corridorMesh: THREE.Mesh | null = null;
  private entranceMesh: THREE.Mesh | null = null;
  private southSupportMesh: THREE.Mesh | null = null;

  private holoRings: { group: THREE.Group; ring1: THREE.Mesh; ring2: THREE.Mesh; ring3: THREE.Mesh } | null = null;

  private statusPollInterval: number | null = null;
  private animationId: number | null = null;
  private clock = new THREE.Clock();
  private reducedMotion = false;

  private onStatusUpdate?: (status: ChiefStatus) => void;
  private onError?: (error: Error) => void;

  private currentStatus: ChiefStatus | null = null;
  private selectedZone: ZoneKey | 'chief' | null = null;

  private boundResize = (event: UIEvent) => this.resize((event.target as Window).innerWidth, (event.target as Window).innerHeight);

  constructor(options: FloorSceneOptions) {
    this.reducedMotion = options.reducedMotion || false;
    this.onStatusUpdate = options.onStatusUpdate;
    this.onError = options.onError;

    // Renderer - crisp pixels, bright background
    this.renderer = new THREE.WebGLRenderer({
      canvas: options.canvas,
      antialias: false,
      alpha: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: false,
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x2a2a3e, 1); // Nice blue-gray background
    this.renderer.shadowMap.enabled = false;
    this.renderer.toneMapping = THREE.NoToneMapping;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x2a2a3e);

    // Orthographic camera - proper Habbo isometric view
    const aspect = window.innerWidth / window.innerHeight;
    const frustumSize = CAMERA_FRUSTUM;
    this.camera = new THREE.OrthographicCamera(
      -frustumSize * aspect / 2,
      frustumSize * aspect / 2,
      frustumSize / 2,
      -frustumSize / 2,
      0.1,
      2000
    );

    // Floor container
    this.floorContainer = new THREE.Group();
    this.floorContainer.name = 'floorContainer';
    this.scene.add(this.floorContainer);

    // Simple render pass
    this.composer = new EffectComposer(this.renderer);
    const renderPass = new RenderPass(this.scene, this.camera);
    this.composer.addPass(renderPass);

    // Systems
    this.floorBuilder = new FloorBuilder();
    this.avatarSystem = new AvatarSystem();
    this.cameraController = new CameraController(this.camera, this.renderer.domElement);

    this.init();
  }

  private async init(): Promise<void> {
    try {
      // Build floor
      this.buildFloor();

      // Create avatars
      this.createAvatars();

      // Setup camera controller - target center of floor
      const floorCenter = this.gridToWorld(GRID_W / 2, GRID_H / 2);
      this.cameraController.setTarget(floorCenter);

      // Force camera to correct position immediately
      this.cameraController.update(0);
      this.camera.position.set(floorCenter.x, 350, floorCenter.z + 495);
      this.camera.lookAt(floorCenter.x, 0, floorCenter.z);

      // Start status polling
      this.startStatusPolling();

      // Start render loop
      this.animate();

      // Window resize
      window.addEventListener('resize', this.boundResize);

      console.log('🏗️ Habbo FloorScene initialized');
    } catch (e) {
      this.onError?.(e instanceof Error ? e : new Error(String(e)));
    }
  }

  private buildFloor(): void {
    const floorGeoms = this.floorBuilder.buildAll({
      zones: ZONES,
      chiefCenter: CHIEF_CENTER,
      entrance: ENTRANCE,
      corridorY: CORRIDOR_Y,
      southSupportY: SOUTH_SUPPORT_Y,
      gridW: GRID_W,
      gridH: GRID_H,
      tileW: TILE_W,
      tileH: TILE_H,
      zoneSize: ZONE_SIZE,
      corridorW: CORRIDOR_W,
    });

    this.floorContainer.add(floorGeoms.zones);
    this.floorContainer.add(floorGeoms.chiefCenter);
    this.floorContainer.add(floorGeoms.corridor);
    this.floorContainer.add(floorGeoms.entrance);
    this.floorContainer.add(floorGeoms.southSupport);
    this.floorContainer.add(floorGeoms.props);

    floorGeoms.zoneMeshes.forEach((mesh, key) => {
      mesh.userData = { zoneKey: key, type: 'zone' };
      this.zoneMeshes.set(key as ZoneKey, mesh);
    });
    this.chiefCenterMesh = floorGeoms.chiefCenterMesh;
    if (this.chiefCenterMesh) this.chiefCenterMesh.userData = { type: 'chief' };
    this.corridorMesh = floorGeoms.corridorMesh;
    this.entranceMesh = floorGeoms.entranceMesh;
    this.southSupportMesh = floorGeoms.southSupportMesh;

    this.holoRings = floorGeoms.holoRings;

    // Lighting for props
    this.addMainLights();
    this.addZoneAccentLights();
  }

  private addMainLights(): void {
    const ambient = new THREE.AmbientLight(0xffffff, 1.0);
    this.scene.add(ambient);

    const dir = new THREE.DirectionalLight(0xffffff, 0.5);
    dir.position.set(200, 400, 200);
    this.scene.add(dir);

    const hemi = new THREE.HemisphereLight(0x00e5ff, 0xffb700, 0.3);
    this.scene.add(hemi);
  }

  private addZoneAccentLights(): void {
    ZONE_KEYS.forEach(key => {
      const zone = ZONES[key];
      const screenPos = this.gridToWorld(zone.x + ZONE_SIZE / 2, zone.y + ZONE_SIZE / 2);
      const light = new THREE.PointLight(zone.accent, 0.4, 200, 2);
      light.position.set(screenPos.x, 50, screenPos.y);
      light.castShadow = false;
      this.floorContainer.add(light);
    });

    const chiefPos = this.gridToWorld(CHIEF_POS.x, CHIEF_POS.y);
    const chiefLight = new THREE.PointLight(0xffd700, 0.6, 200, 2);
    chiefLight.position.set(chiefPos.x, 80, chiefPos.y);
    this.floorContainer.add(chiefLight);
  }

  private createAvatars(): void {
    // Operator
    this.avatarSystem.createAvatar({
      id: 'operator',
      type: 'operator',
      gridX: OPERATOR_START.x,
      gridY: OPERATOR_START.y,
      color: 0x4488ff,
    });

    // Chief
    this.avatarSystem.createAvatar({
      id: 'chief',
      type: 'chief',
      gridX: CHIEF_POS.x,
      gridY: CHIEF_POS.y,
      color: 0xffd700,
      isChief: true,
    });

    // Zone agents
    ZONE_KEYS.forEach(key => {
      const zone = ZONES[key];
      this.avatarSystem.createAvatar({
        id: key,
        type: key,
        gridX: zone.x + ZONE_SIZE / 2 + (Math.random() - 0.5) * 4,
        gridY: zone.y + ZONE_SIZE / 2 + (Math.random() - 0.5) * 4,
        color: zone.color,
      });
    });

    this.avatarSystem.getAllMeshes().forEach(mesh => {
      this.scene.add(mesh);
    });
  }

  private startStatusPolling(): void {
    const isCodespace = window.location.hostname.includes('github.dev') || window.location.hostname.includes('app.github.dev');
    
    if (isCodespace) {
      console.log('📡 Codespace detected: using mock data');
      this.useMockStatus();
      this.statusPollInterval = window.setInterval(() => this.useMockStatus(), 2000);
    } else {
      this.pollStatus();
      this.statusPollInterval = window.setInterval(() => this.pollStatus(), 2000);
    }
  }

  private async pollStatus(): Promise<void> {
    try {
      const apiClient = await getApiClient();
      const status = await apiClient.getStatus();
      this.currentStatus = status;
      this.updateFromStatus(status);
      this.onStatusUpdate?.(status);
    } catch (e) {
      console.warn('Status poll failed:', e);
      this.useMockStatus();
    }
  }

  private useMockStatus(): void {
    const mockStatus: any = {
      nightly: { state: 'running', hypotheses_generated: 847, hypotheses_passed: 12, hypotheses_rejected: 835, last_error: null },
      paper_strategies: {
        'strat_1': { strategy_id: 'strat_1', name: 'ema_trend_nq_5m', symbol: 'NQ', timeframe: '5m', regime: 'trend_up', state: 'paper', equity: 52847, unrealized_pnl: 1234, realized_pnl: -456, trades_today: 23, win_rate: 0.61, avg_fill_slippage_bps: 1.2, last_signal: 'LONG 2 MNQ @ 15420', last_fill: 'LONG 2 @ 15421', guard_alerts: [] },
      },
      guardian_alerts: [],
      guardian_status: { kill_switch: false, loss_streak: 0, trades_today: 47, daily_pnl: 1234.56, trailing_dd: 2.1, limits: {} },
    };
    this.currentStatus = mockStatus;
    this.updateFromStatus(mockStatus);
    this.onStatusUpdate?.(mockStatus);
  }

  private updateFromStatus(status: ChiefStatus): void {
    this.avatarSystem.updateFromStatus(status);
    this.updateZoneVisuals(status);
  }

  private updateZoneVisuals(status: ChiefStatus): void {
    Object.entries(status.paper_strategies).forEach(([id, strat]) => {
      const zoneKey = this.getZoneForStrategy(strat);
      if (zoneKey && this.zoneMeshes.has(zoneKey)) {
        const mesh = this.zoneMeshes.get(zoneKey)!;
        const material = mesh.material as THREE.MeshBasicMaterial;
        if (material) {
          material.opacity = strat.trades_today > 0 ? 1.0 : 0.9;
        }
      }
    });

    if (this.chiefCenterMesh && this.chiefCenterMesh.material) {
      const material = this.chiefCenterMesh.material as THREE.MeshBasicMaterial;
      if (material) {
        material.opacity = status.guardian_status?.kill_switch ? 0.5 : 1.0;
      }
    }
  }

  private getZoneForStrategy(strat: PaperStrategy): ZoneKey | null {
    const regime = strat.regime as ZoneKey;
    if (ZONES[regime]) return regime;
    return null;
  }

  private gridToWorld(gx: number, gy: number): { x: number; y: number; z: number } {
    const screen = gridToScreen(gx, gy);
    return { x: screen.x, y: 0, z: screen.y };
  }

  private getOperatorPosition(): THREE.Vector3 {
    const op = this.avatarSystem.getAvatar('operator');
    if (op) {
      const worldPos = this.avatarSystem.gridToWorld(op.gridX, op.gridY);
      return new THREE.Vector3(worldPos.x, 0, worldPos.y);
    }
    const startPos = this.gridToWorld(OPERATOR_START.x, OPERATOR_START.y);
    return new THREE.Vector3(startPos.x, 0, startPos.y);
  }

  private animate(): void {
    this.animationId = requestAnimationFrame(() => this.animate());

    const delta = this.clock.getDelta();

    this.cameraController.update(delta);

    // Animate Chief holographic rings
    if (this.holoRings) {
      const t = this.clock.getElapsedTime();
      this.holoRings.group.rotation.z += delta * 0.2;
      const bob = Math.sin(t * 0.8) * 2;
      this.holoRings.group.position.y = bob;
    }

    const opPos = this.getOperatorPosition();
    this.cameraController.setTarget(opPos);

    this.composer.render(delta);
  }

  public resize(width: number, height: number): void {
    const aspect = width / height;
    const frustumSize = CAMERA_FRUSTUM;
    this.camera.left = -frustumSize * aspect / 2;
    this.camera.right = frustumSize * aspect / 2;
    this.camera.top = frustumSize / 2;
    this.camera.bottom = -frustumSize / 2;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
    this.composer.setSize(width, height);
    this.cameraController.resize(width, height);
  }

  public selectZone(zoneKey: ZoneKey | 'chief'): void {
    this.selectedZone = zoneKey;
    this.zoneMeshes.forEach((mesh, key) => {
      const material = mesh.material as THREE.MeshBasicMaterial;
      material.opacity = key === zoneKey ? 1.0 : 0.9;
    });
    if (this.chiefCenterMesh && zoneKey === 'chief') {
      (this.chiefCenterMesh.material as THREE.MeshBasicMaterial).opacity = 1.0;
    }
  }

  public clearSelection(): void {
    this.selectedZone = null;
    this.zoneMeshes.forEach(mesh => {
      (mesh.material as THREE.MeshBasicMaterial).opacity = 0.9;
    });
    if (this.chiefCenterMesh) {
      (this.chiefCenterMesh.material as THREE.MeshBasicMaterial).opacity = 1.0;
    }
  }

  public async sendCommand(type: string, data: any = {}): Promise<void> {
    try {
      const apiClient = await getApiClient();
      await apiClient.sendCommand({ type, ...data });
    } catch (e) {
      console.error('Command failed:', e);
      this.onError?.(e instanceof Error ? e : new Error(String(e)));
    }
  }

  public getCameraController(): CameraController {
    return this.cameraController;
  }

  public getAvatarSystem(): AvatarSystem {
    return this.avatarSystem;
  }

  public getFloorContainer(): THREE.Group {
    return this.floorContainer;
  }

  public setReducedMotion(enabled: boolean): void {
    this.reducedMotion = enabled;
    this.cameraController.setReducedMotion(enabled);
    this.avatarSystem.setReducedMotion(enabled);
  }

  public dispose(): void {
    if (this.animationId) cancelAnimationFrame(this.animationId);
    if (this.statusPollInterval) clearInterval(this.statusPollInterval);

    this.avatarSystem.dispose();
    this.cameraController.dispose();
    this.composer.dispose();
    this.renderer.dispose();

    window.removeEventListener('resize', this.boundResize);
  }
}