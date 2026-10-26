/** Main Three.js scene setup */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FloorBuilder } from './FloorBuilder.js';
import { AvatarSystem } from './AvatarSystem.js';
import { CameraController } from './CameraController.js';
import { createScanlineShader, createVignetteShader } from './Effects.js';
import { preloadAssets, createPlaceholderTexture } from '../utils/assets.js';
import { getApiClient } from '../net/ApiClient.js';
import {
  TILE_W, TILE_H, GRID_W, GRID_H, ZONE_SIZE, CORRIDOR_W,
  ZONES, CHIEF_CENTER, ENTRANCE, CORRIDOR_Y, SOUTH_SUPPORT_Y,
  OPERATOR_START, CHIEF_POS, ZONE_KEYS,
  CAMERA_DEFAULTS, LIGHTING, POST_PROCESSING, REDUCED_MOTION_DEFAULTS,
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

  private statusPollInterval: number | null = null;
  private animationId: number | null = null;
  private clock = new THREE.Clock();
  private reducedMotion = false;

  // Callbacks
  private onStatusUpdate?: (status: ChiefStatus) => void;
  private onError?: (error: Error) => void;

  // State
  private currentStatus: ChiefStatus | null = null;
  private selectedZone: ZoneKey | 'chief' | null = null;

  // Bound resize handler for proper removal
  private boundResize = (event: UIEvent) => this.resize(event.currentTarget.innerWidth, event.currentTarget.innerHeight);

  constructor(options: FloorSceneOptions) {
    this.reducedMotion = options.reducedMotion || false;
    this.onStatusUpdate = options.onStatusUpdate;
    this.onError = options.onError;

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: options.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: false,
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x0a0a0f, 1);
    this.renderer.shadowMap.enabled = false; // We use baked lighting
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0a0f);

    // Orthographic camera for isometric view
    const aspect = window.innerWidth / window.innerHeight;
    const frustumSize = 100;
    this.camera = new THREE.OrthographicCamera(
      -frustumSize * aspect / 2,
      frustumSize * aspect / 2,
      frustumSize / 2,
      -frustumSize / 2,
      0.1,
      2000
    );
    this.camera.position.set(0, 200, 0);
    this.camera.lookAt(0, 0, 0);
    this.camera.zoom = CAMERA_DEFAULTS.zoom;

    // Floor container (all floor geometry)
    this.floorContainer = new THREE.Group();
    this.floorContainer.name = 'floorContainer';
    this.scene.add(this.floorContainer);

    // Post-processing
    this.composer = new EffectComposer(this.renderer);
    this.setupPostProcessing();

    // Systems
    this.floorBuilder = new FloorBuilder();
    this.avatarSystem = new AvatarSystem();
    this.cameraController = new CameraController(this.camera, this.renderer.domElement);

    // Start
    this.init();
  }

  private setupPostProcessing(): void {
    // Render pass
    const renderPass = new RenderPass(this.scene, this.camera);
    this.composer.addPass(renderPass);

    // Bloom pass
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      POST_PROCESSING.bloom.strength,
      POST_PROCESSING.bloom.radius,
      POST_PROCESSING.bloom.threshold
    );
    bloomPass.threshold = POST_PROCESSING.bloom.threshold;
    bloomPass.strength = POST_PROCESSING.bloom.strength;
    bloomPass.radius = POST_PROCESSING.bloom.radius;
    this.composer.addPass(bloomPass);
    (this.composer as any).bloomPass = bloomPass;

    // Scanlines
    const scanlinePass = new ShaderPass(createScanlineShader());
    scanlinePass.uniforms.opacity.value = POST_PROCESSING.scanlines.opacity;
    scanlinePass.uniforms.scale.value = POST_PROCESSING.scanlines.scale;
    this.composer.addPass(scanlinePass);
    (this.composer as any).scanlinePass = scanlinePass;

    // Vignette
    const vignettePass = new ShaderPass(createVignetteShader());
    vignettePass.uniforms.offset.value = POST_PROCESSING.vignette.offset;
    vignettePass.uniforms.darkness.value = POST_PROCESSING.vignette.darkness;
    this.composer.addPass(vignettePass);
  }

  private async init(): Promise<void> {
    try {
      // Load assets (placeholders for now)
      await this.loadAssets();

      // Build floor
      this.buildFloor();

      // Create avatars
      this.createAvatars();

      // Setup camera controller
      this.cameraController.setTarget(this.getOperatorPosition());
      this.cameraController.setReducedMotion(this.reducedMotion);

      // Start status polling
      this.startStatusPolling();

      // Start render loop
      this.animate();

      // Window resize
      window.addEventListener('resize', this.boundResize);

      console.log('🏗️ FloorScene initialized');
    } catch (e) {
      this.onError?.(e instanceof Error ? e : new Error(String(e)));
    }
  }

  private async loadAssets(): Promise<void> {
    // For now, use placeholder textures
    // In production, load from /assets/sprites/
    console.log('Assets loaded (placeholders)');
  }

  private buildFloor(): void {
    // Build all floor geometry
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

    // Add to floor container
    this.floorContainer.add(floorGeoms.zones);
    this.floorContainer.add(floorGeoms.chiefCenter);
    this.floorContainer.add(floorGeoms.corridor);
    this.floorContainer.add(floorGeoms.entrance);
    this.floorContainer.add(floorGeoms.southSupport);

    // Store references for interaction
    floorGeoms.zoneMeshes.forEach((mesh, key) => {
      mesh.userData = { zoneKey: key, type: 'zone' };
      this.zoneMeshes.set(key as ZoneKey, mesh);
    });
    this.chiefCenterMesh = floorGeoms.chiefCenterMesh;
    if (this.chiefCenterMesh) this.chiefCenterMesh.userData = { type: 'chief' };
    this.corridorMesh = floorGeoms.corridorMesh;
    this.entranceMesh = floorGeoms.entranceMesh;
    this.southSupportMesh = floorGeoms.southSupportMesh;

    // Add zone accent lights
    this.addZoneAccentLights();
  }

  private addZoneAccentLights(): void {
    ZONE_KEYS.forEach(key => {
      const zone = ZONES[key];
      const screenPos = this.gridToWorld(zone.x + ZONE_SIZE / 2, zone.y + ZONE_SIZE / 2);
      const light = new THREE.PointLight(zone.accent, LIGHTING.zoneAccent.intensity, LIGHTING.zoneAccent.distance, LIGHTING.zoneAccent.decay);
      light.position.set(screenPos.x, 50, screenPos.y);
      light.castShadow = false;
      this.floorContainer.add(light);
    });

    // Chief center accent light
    const chiefPos = this.gridToWorld(CHIEF_POS.x, CHIEF_POS.y);
    const chiefLight = new THREE.PointLight(0xffcc00, 0.5, 150, 2);
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
      color: 0xffcc00,
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

    // Add avatar meshes to scene
    this.avatarSystem.getAllMeshes().forEach(mesh => {
      this.scene.add(mesh);
    });
  }

  private startStatusPolling(): void {
    this.pollStatus();
    this.statusPollInterval = window.setInterval(() => this.pollStatus(), 2000);
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
      // Use mock data
      this.useMockStatus();
    }
  }

  private useMockStatus(): void {
    // Mock status for development
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
    // Update avatar system with live data
    this.avatarSystem.updateFromStatus(status);

    // Update zone visual indicators
    this.updateZoneVisuals(status);
  }

  private updateZoneVisuals(status: ChiefStatus): void {
    // Update zone materials based on activity
    Object.entries(status.paper_strategies).forEach(([id, strat]) => {
      const zoneKey = this.getZoneForStrategy(strat);
      if (zoneKey && this.zoneMeshes.has(zoneKey)) {
        const mesh = this.zoneMeshes.get(zoneKey)!;
        const material = mesh.material as THREE.MeshStandardMaterial;
        // Pulse emission based on activity
        const intensity = strat.trades_today > 0 ? 0.3 : 0.1;
        material.emissiveIntensity = intensity;
      }
    });

    // Guardian kill switch visual
    if (this.chiefCenterMesh) {
      const material = this.chiefCenterMesh.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = status.guardian_status.kill_switch ? 1.0 : 0.2;
      material.emissive.setHex(status.guardian_status.kill_switch ? 0xff4757 : 0x00d4aa);
    }
  }

  private getZoneForStrategy(strat: PaperStrategy): ZoneKey | null {
    // Map strategy to zone based on regime/symbol
    const regime = strat.regime as ZoneKey;
    if (ZONES[regime]) return regime;
    return null;
  }

  private gridToWorld(gx: number, gy: number): { x: number; y: number; z: number } {
    const screen = this.floorBuilder.gridToScreen(gx, gy);
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

  // Public API
  public setReducedMotion(enabled: boolean): void {
    this.reducedMotion = enabled;
    this.cameraController.setReducedMotion(enabled);
    this.avatarSystem.setReducedMotion(enabled);

    // Update post-processing
    const bloomPass = (this.composer as any).bloomPass;
    const scanlinePass = (this.composer as any).scanlinePass;
    if (bloomPass) bloomPass.enabled = !enabled || !REDUCED_MOTION_DEFAULTS.disableBloom;
    if (scanlinePass) scanlinePass.enabled = !enabled || !REDUCED_MOTION_DEFAULTS.disableScanlines;
  }

  public selectZone(zoneKey: ZoneKey | 'chief'): void {
    this.selectedZone = zoneKey;
    // Visual feedback
    this.zoneMeshes.forEach((mesh, key) => {
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = key === zoneKey ? 0.5 : 0.1;
    });
    if (this.chiefCenterMesh && zoneKey === 'chief') {
      (this.chiefCenterMesh.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.8;
    }
  }

  public clearSelection(): void {
    this.selectedZone = null;
    this.zoneMeshes.forEach(mesh => {
      (mesh.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.1;
    });
    if (this.chiefCenterMesh) {
      (this.chiefCenterMesh.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.2;
    }
  }

  public async sendCommand(type: string, data: any = {}): Promise<void> {
    try {
      const apiClient = await getApiClient();
      await apiClient.sendCommand({ type, ...data });
      // Optimistic update - will be confirmed by next poll
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

  // Render loop
  private animate(): void {
    this.animationId = requestAnimationFrame(() => this.animate());

    const delta = this.clock.getDelta();

    // Update camera controller
    this.cameraController.update(delta);

    // Update avatars
    this.avatarSystem.update(delta, this.reducedMotion);

    // Update camera target (follow operator)
    const opPos = this.getOperatorPosition();
    this.cameraController.setTarget(opPos);

    // Render
    this.composer.render(delta);
  }

  // Resize handler
  public resize(width: number, height: number): void {
    const aspect = width / height;
    const frustumSize = 100;
    this.camera.left = -frustumSize * aspect / 2;
    this.camera.right = frustumSize * aspect / 2;
    this.camera.top = frustumSize / 2;
    this.camera.bottom = -frustumSize / 2;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
    this.composer.setSize(width, height);
    this.cameraController.resize(width, height);

    // Update post-processing passes
    const bloomPass = (this.composer as any).bloomPass;
    if (bloomPass) bloomPass.setSize(width, height);
  }

  // Cleanup
  public dispose(): void {
    if (this.animationId) cancelAnimationFrame(this.animationId);
    if (this.statusPollInterval) clearInterval(this.statusPollInterval);

    this.avatarSystem.dispose();
    this.cameraController.dispose();
    this.composer.dispose();
    this.renderer.dispose();

    // Remove event listeners
    window.removeEventListener('resize', this.boundResize);
  }
}