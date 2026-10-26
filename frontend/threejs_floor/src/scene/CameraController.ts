/** Camera controller for classic Habbo isometric view (2:1 dimetric).
 *  Camera positioned at ~26.5° elevation (arctan(0.5)) and 225° azimuth (south-west)
 *  so floor tiles appear as 2:1 diamonds, walls are visible, avatars from side. */

import * as THREE from 'three';
import { CAMERA_DEFAULTS, CAMERA_FRUSTUM, HABBO_CAM, REDUCED_MOTION_DEFAULTS } from '../data/floorConfig.js';

export interface CameraTarget {
  x: number;
  y: number;
  z: number;
}

export class CameraController {
  private camera: THREE.OrthographicCamera;
  private domElement: HTMLElement;

  private target: CameraTarget = { x: 0, y: 0, z: 0 };
  private currentTarget: CameraTarget = { x: 0, y: 0, z: 0 };
  private zoom = CAMERA_DEFAULTS.zoom;
  private minZoom = CAMERA_DEFAULTS.minZoom;
  private maxZoom = CAMERA_DEFAULTS.maxZoom;
  private lerpFactor = CAMERA_DEFAULTS.lerpFactor;

  private reducedMotion = false;
  private aspect = 1;

  // Interaction state
  private isDragging = false;
  private lastMouseX = 0;
  private lastMouseY = 0;

  // Focus modes
  private focusMode: 'follow' | 'fixed' | 'chief' = 'follow';
  private fixedTarget: CameraTarget | null = null;
  private initialized = false;

  constructor(camera: THREE.OrthographicCamera, domElement: HTMLElement) {
    this.camera = camera;
    this.domElement = domElement;
    this.setupEventListeners();
  }

  private setupEventListeners(): void {
    this.domElement.addEventListener('wheel', this.onWheel.bind(this), { passive: false });
    this.domElement.addEventListener('pointerdown', this.onPointerDown.bind(this));
    this.domElement.addEventListener('pointermove', this.onPointerMove.bind(this));
    this.domElement.addEventListener('pointerup', this.onPointerUp.bind(this));
    this.domElement.addEventListener('pointerleave', this.onPointerUp.bind(this));
    this.domElement.addEventListener('contextmenu', e => e.preventDefault());

    // Touch support
    this.domElement.addEventListener('touchstart', this.onTouchStart.bind(this), { passive: false });
    this.domElement.addEventListener('touchmove', this.onTouchMove.bind(this), { passive: false });
    this.domElement.addEventListener('touchend', this.onTouchEnd.bind(this));
  }

  private onWheel(event: WheelEvent): void {
    event.preventDefault();
    const delta = event.deltaY > 0 ? 1.15 : 1 / 1.15;
    this.setZoom(this.zoom * delta);
  }

  private onPointerDown(event: PointerEvent): void {
    if (event.button === 1 || event.button === 2) { // Middle or right click
      event.preventDefault();
      this.isDragging = true;
      this.lastMouseX = event.clientX;
      this.lastMouseY = event.clientY;
      this.domElement.style.cursor = 'grabbing';
    }
  }

  private onPointerMove(event: PointerEvent): void {
    if (!this.isDragging) return;
    event.preventDefault();

    const dx = event.clientX - this.lastMouseX;
    const dy = event.clientY - this.lastMouseY;

    // Pan camera target - isometric mapping
    const panSpeed = 0.5 / this.zoom;
    this.target.x -= (dx + dy) * panSpeed * 0.5;
    this.target.z -= (dy - dx) * panSpeed * 0.5;

    this.lastMouseX = event.clientX;
    this.lastMouseY = event.clientY;

    this.focusMode = 'fixed';
  }

  private onPointerUp(): void {
    this.isDragging = false;
    this.domElement.style.cursor = 'grab';
  }

  private onTouchStart(event: TouchEvent): void {
    if (event.touches.length === 1) {
      this.lastMouseX = event.touches[0].clientX;
      this.lastMouseY = event.touches[0].clientY;
    }
  }

  private onTouchMove(event: TouchEvent): void {
    if (event.touches.length === 1) {
      event.preventDefault();
      const dx = event.touches[0].clientX - this.lastMouseX;
      const dy = event.touches[0].clientY - this.lastMouseY;
      const panSpeed = 0.5 / this.zoom;
      this.target.x -= (dx + dy) * panSpeed * 0.5;
      this.target.z -= (dy - dx) * panSpeed * 0.5;
      this.lastMouseX = event.touches[0].clientX;
      this.lastMouseY = event.touches[0].clientY;
      this.focusMode = 'fixed';
    }
  }

  private onTouchEnd(): void {}

  public update(delta: number): void {
    // Smooth target interpolation
    if (!this.reducedMotion || !REDUCED_MOTION_DEFAULTS.disableCameraLerp) {
      this.currentTarget.x += (this.target.x - this.currentTarget.x) * this.lerpFactor;
      this.currentTarget.y += (this.target.y - this.currentTarget.y) * this.lerpFactor;
      this.currentTarget.z += (this.target.z - this.currentTarget.z) * this.lerpFactor;
    } else {
      this.currentTarget = { ...this.target };
    }

    // Classic Habbo isometric camera position
    // Camera at 26.565° elevation, 225° azimuth (south-west of target)
    const camX = this.currentTarget.x - HABBO_CAM.OFFSET / this.zoom;
    const camY = HABBO_CAM.HEIGHT / this.zoom;
    const camZ = this.currentTarget.z + HABBO_CAM.OFFSET / this.zoom;

    // Smooth camera movement
    const lerp = this.reducedMotion ? 1 : this.lerpFactor;
    this.camera.position.x += (camX - this.camera.position.x) * lerp;
    this.camera.position.y += (camY - this.camera.position.y) * lerp;
    this.camera.position.z += (camZ - this.camera.position.z) * lerp;

    // Look at target (at ground level)
    this.camera.lookAt(this.currentTarget.x, 0, this.currentTarget.z);

    // Update zoom
    this.camera.zoom += (this.zoom - this.camera.zoom) * (this.reducedMotion ? 1 : 0.1);
    this.camera.updateProjectionMatrix();
  }

  public setTarget(target: CameraTarget): void {
    if (this.focusMode === 'follow') {
      this.target = { ...target };
      // Snap on the very first target
      if (!this.initialized) {
        this.initialized = true;
        this.currentTarget = { ...target };
        this.camera.position.set(
          target.x - HABBO_CAM.OFFSET,
          HABBO_CAM.HEIGHT,
          target.z + HABBO_CAM.OFFSET
        );
      }
    }
  }

  public setZoom(zoom: number): void {
    this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, zoom));
  }

  public getZoom(): number {
    return this.zoom;
  }

  public setReducedMotion(enabled: boolean): void {
    this.reducedMotion = enabled;
    if (enabled) {
      this.lerpFactor = 1; // Instant
    } else {
      this.lerpFactor = CAMERA_DEFAULTS.lerpFactor;
    }
  }

  public setFocusMode(mode: 'follow' | 'fixed' | 'chief', target?: CameraTarget): void {
    this.focusMode = mode;
    if (mode === 'fixed' && target) {
      this.fixedTarget = target;
      this.target = { ...target };
    } else if (mode === 'chief') {
      this.focusMode = 'fixed';
    } else if (mode === 'follow') {
      this.fixedTarget = null;
    }
  }

  public getFocusMode(): string {
    return this.focusMode;
  }

  public focusOnChief(chiefPosition: { x: number; y: number; z: number }): void {
    this.focusMode = 'fixed';
    this.target = { x: chiefPosition.x, y: 0, z: chiefPosition.z };
    this.zoom = 1.3;
  }

  public resize(width: number, height: number): void {
    this.aspect = width / height;
    const aspect = this.aspect;
    const frustumSize = CAMERA_FRUSTUM;
    this.camera.left = -frustumSize * aspect / 2;
    this.camera.right = frustumSize * aspect / 2;
    this.camera.top = frustumSize / 2;
    this.camera.bottom = -frustumSize / 2;
    this.camera.updateProjectionMatrix();
  }

  public dispose(): void {
    this.domElement.removeEventListener('wheel', this.onWheel.bind(this));
    this.domElement.removeEventListener('pointerdown', this.onPointerDown.bind(this));
    this.domElement.removeEventListener('pointermove', this.onPointerMove.bind(this));
    this.domElement.removeEventListener('pointerup', this.onPointerUp.bind(this));
    this.domElement.removeEventListener('pointerleave', this.onPointerUp.bind(this));
    this.domElement.removeEventListener('touchstart', this.onTouchStart.bind(this));
    this.domElement.removeEventListener('touchmove', this.onTouchMove.bind(this));
    this.domElement.removeEventListener('touchend', this.onTouchEnd.bind(this));
  }

  // Getters
  public getTarget(): CameraTarget {
    return { ...this.target };
  }

  public getCurrentTarget(): CameraTarget {
    return { ...this.currentTarget };
  }
}