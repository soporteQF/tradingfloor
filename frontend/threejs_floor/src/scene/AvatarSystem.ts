/** Avatar system for Habbo-style sprites */

import * as THREE from 'three';
import { createAvatarTexture } from '../utils/assets.js';
import { gridToScreen } from '../utils/iso.js';
import { AVATAR_COLORS, AvatarType, TILE_W, TILE_H } from '../data/floorConfig.js';

export interface AvatarConfig {
  id: string;
  type: AvatarType;
  gridX: number;
  gridY: number;
  targetGridX?: number;
  targetGridY?: number;
  color: number;
  isChief?: boolean;
}

export interface AvatarState {
  id: string;
  type: AvatarType;
  gridX: number;
  gridY: number;
  targetGridX: number;
  targetGridY: number;
  color: number;
  isChief: boolean;
  isWalking: boolean;
  direction: 'up' | 'down' | 'left' | 'right';
  walkFrame: number;
  walkTimer: number;
  bobPhase: number;
  bobAmount: number;
  speed: number;
  voiceRingActive: boolean;
  voiceRingTimer: number;
  voiceRingMesh: THREE.Mesh | null;
  mesh: THREE.Sprite;
  labelMesh: THREE.Mesh | null;
}

export class AvatarSystem {
  private avatars: Map<string, AvatarState> = new Map();
  private avatarMeshes: Map<string, THREE.Sprite> = new Map();
  private textures: Map<AvatarType, THREE.Texture> = new Map();
  private labelSprites: Map<string, THREE.Sprite> = new Map();

  constructor() {
    this.initTextures();
  }

  private initTextures(): void {
    // Create placeholder textures for each avatar type
    Object.entries(AVATAR_COLORS).forEach(([type, color]) => {
      const avatarType = type as AvatarType;
      this.textures.set(avatarType, createAvatarTexture(color, avatarType === 'chief' ? 'chief' : avatarType === 'operator' ? 'operator' : 'agent'));
    });
  }

  public createAvatar(config: AvatarConfig): void {
    const texture = this.textures.get(config.type) || this.textures.get('research')!;

    // Create sprite material
    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      alphaTest: 0.1,
      depthWrite: false,
      sizeAttenuation: false, // Keep constant size in screen space
    });

    const sprite = new THREE.Sprite(material);
    sprite.name = `avatar_${config.id}`;
    sprite.renderOrder = 10; // Render on top of floor

    // Size in world units (Habbo avatar ~1.5 tiles tall)
    const avatarHeight = TILE_H * 2.5; // ~80 world units
    const aspect = 1; // Square-ish
    sprite.scale.set(avatarHeight * aspect, avatarHeight, 1);

    // Position
    const worldPos = this.gridToWorld(config.gridX, config.gridY);
    sprite.position.set(worldPos.x, avatarHeight / 2, worldPos.z);
    sprite.center.set(0.5, 0); // Bottom center

    // Store state
    const state: AvatarState = {
      id: config.id,
      type: config.type,
      gridX: config.gridX,
      gridY: config.gridY,
      targetGridX: config.targetGridX ?? config.gridX,
      targetGridY: config.targetGridY ?? config.gridY,
      color: config.color,
      isChief: config.isChief || false,
      isWalking: false,
      direction: 'down',
      walkFrame: 0,
      walkTimer: 0,
      bobPhase: Math.random() * Math.PI * 2,
      bobAmount: config.isChief ? 2 : 1.5,
      speed: 8, // tiles per second
      voiceRingActive: false,
      voiceRingTimer: 0,
      voiceRingMesh: null,
      mesh: sprite,
      labelMesh: null,
    };

    // Add label
    this.addLabel(config.id, config.type, sprite);

    // Voice ring (for chief TTS)
    if (config.isChief) {
      this.addVoiceRing(state);
    }

    this.avatars.set(config.id, state);
    this.avatarMeshes.set(config.id, sprite);
  }

  private addLabel(id: string, type: string, sprite: THREE.Sprite): void {
    // Create canvas texture for label
    const canvas = document.createElement('canvas');
    canvas.width = 128; canvas.height = 32;
    const ctx = canvas.getContext('2d')!;
    ctx.font = 'bold 14px "JetBrains Mono"';
    ctx.fillStyle = '#7a7a8a';
    ctx.strokeStyle = '#0a0a0f';
    ctx.lineWidth = 3;
    const text = type.toUpperCase();
    const metrics = ctx.measureText(text);
    ctx.strokeText(text, (128 - metrics.width) / 2, 20);
    ctx.fillText(text, (128 - metrics.width) / 2, 20);

    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;

    const labelMaterial = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      depthWrite: false,
      sizeAttenuation: false,
    });

    const labelSprite = new THREE.Sprite(labelMaterial);
    labelSprite.name = `label_${id}`;
    labelSprite.scale.set(64, 16, 1);
    labelSprite.position.set(0, -10, 0); // Above avatar
    labelSprite.renderOrder = 11;

    sprite.add(labelSprite);
    this.labelSprites.set(id, labelSprite);
  }

  private addVoiceRing(state: AvatarState): void {
    const ringGeometry = new THREE.RingGeometry(40, 48, 32);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0x00d4aa,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    const ringMesh = new THREE.Mesh(ringGeometry, ringMaterial);
    ringMesh.rotation.x = -Math.PI / 2;
    ringMesh.position.y = -5;
    ringMesh.scale.set(1, 1, 1);
    ringMesh.visible = false;

    state.mesh.add(ringMesh);
    state.voiceRingMesh = ringMesh;
  }

  public getAvatar(id: string): AvatarState | undefined {
    return this.avatars.get(id);
  }

  public getAvatarMesh(id: string): THREE.Sprite | undefined {
    return this.avatarMeshes.get(id);
  }

  public getAllMeshes(): THREE.Sprite[] {
    return Array.from(this.avatarMeshes.values());
  }

  public getAllAvatars(): AvatarState[] {
    return Array.from(this.avatars.values());
  }

  public gridToWorld(gx: number, gy: number): { x: number; y: number; z: number } {
    const screen = gridToScreen(gx, gy);
    return { x: screen.x, y: 0, z: screen.y };
  }

  public update(delta: number, reducedMotion: boolean): void {
    this.avatars.forEach(state => this.updateAvatar(state, delta, reducedMotion));
  }

  private updateAvatar(state: AvatarState, delta: number, reducedMotion: boolean): void {
    const { mesh } = state;

    // Movement towards target
    const dx = state.targetGridX - state.gridX;
    const dy = state.targetGridY - state.gridY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist > 0.05) {
      state.isWalking = true;
      const speed = state.speed * delta;
      const moveX = Math.abs(dx) > Math.abs(dy)
        ? Math.sign(dx) * Math.min(speed, Math.abs(dx))
        : dx * (speed / (dist || 1));
      const moveY = Math.abs(dy) > Math.abs(dx)
        ? Math.sign(dy) * Math.min(speed, Math.abs(dy))
        : dy * (speed / (dist || 1));

      state.gridX += moveX;
      state.gridY += moveY;

      // Update direction
      if (Math.abs(moveX) > Math.abs(moveY)) {
        state.direction = moveX > 0 ? 'right' : 'left';
      } else {
        state.direction = moveY > 0 ? 'down' : 'up';
      }

      // Walk animation
      state.walkTimer += delta * 10;
      if (state.walkTimer >= 1) {
        state.walkTimer = 0;
        state.walkFrame = (state.walkFrame + 1) % 4;
        if (!reducedMotion) {
          mesh.scale.y = state.walkFrame % 2 === 0 ? 1.0 : 0.95;
        }
      }
    } else {
      state.isWalking = false;
      state.gridX = state.targetGridX;
      state.gridY = state.targetGridY;
      state.walkFrame = 0;
      mesh.scale.y = 1;
    }

    // Bob animation (idle)
    if (!state.isWalking && !reducedMotion) {
      if (state.isChief) {
        state.bobPhase += delta * 1.5;
        mesh.position.y = Math.sin(state.bobPhase) * state.bobAmount + mesh.scale.y / 2;

        // Voice ring pulse
        if (state.voiceRingActive && state.voiceRingMesh) {
          state.voiceRingTimer -= delta;
          const pulse = Math.sin(state.voiceRingTimer * 20) * 0.5 + 0.5;
          (state.voiceRingMesh.material as THREE.MeshBasicMaterial).opacity = pulse * 0.6;
          state.voiceRingMesh.scale.setScalar(1 + pulse * 0.3);
          state.voiceRingMesh.visible = true;
          if (state.voiceRingTimer <= 0) {
            state.voiceRingActive = false;
            (state.voiceRingMesh.material as THREE.MeshBasicMaterial).opacity = 0;
            state.voiceRingMesh.scale.setScalar(1);
            state.voiceRingMesh.visible = false;
          }
        }
      } else {
        state.bobPhase += delta * 3;
        mesh.position.y = Math.sin(state.bobPhase) * state.bobAmount + mesh.scale.y / 2;
      }
    }

    // Update world position
    const worldPos = this.gridToWorld(state.gridX, state.gridY);
    mesh.position.x = worldPos.x;
    mesh.position.z = worldPos.z;
    mesh.position.y = mesh.position.y; // Keep bob offset

    // Face camera (sprites auto-face camera, but we can rotate for direction)
    // For now, sprites always face camera - direction could be shown via texture frames
  }

  public setAvatarTarget(id: string, gridX: number, gridY: number): void {
    const state = this.avatars.get(id);
    if (state) {
      state.targetGridX = gridX;
      state.targetGridY = gridY;
    }
  }

  public triggerVoice(id: string, duration: number = 2): void {
    const state = this.avatars.get(id);
    if (state && state.isChief && state.voiceRingMesh) {
      state.voiceRingActive = true;
      state.voiceRingTimer = duration;
      state.voiceRingMesh.visible = true;
      (state.voiceRingMesh.material as THREE.MeshBasicMaterial).opacity = 0.6;
      state.voiceRingMesh.scale.setScalar(1);
    }
  }

  public setReducedMotion(enabled: boolean): void {
    this.avatars.forEach(state => {
      state.mesh.scale.y = 1;
      if (state.voiceRingMesh) {
        (state.voiceRingMesh.material as THREE.MeshBasicMaterial).opacity = 0;
        state.voiceRingMesh.visible = false;
      }
    });
  }

  public updateFromStatus(status: any): void {
    // Update paper strategy avatars based on live data
    // For now, just update chief voice ring on alerts
    if (status.guardian_alerts && status.guardian_alerts.length > 0) {
      this.triggerVoice('chief', 2);
    }
    if (status.nightly?.state === 'running' && Math.random() < 0.1) {
      // Occasional chief voice during nightly
    }
  }

  public dispose(): void {
    this.avatars.forEach(state => {
      if (state.mesh.parent) state.mesh.parent.remove(state.mesh);
      (state.mesh.material as THREE.Material).dispose();
      if (state.voiceRingMesh) {
        state.voiceRingMesh.geometry.dispose();
        (state.voiceRingMesh.material as THREE.Material).dispose();
      }
    });
    this.avatars.clear();
    this.avatarMeshes.clear();
    this.textures.forEach(t => t.dispose());
    this.textures.clear();
    this.labelSprites.forEach(s => s.material.dispose());
    this.labelSprites.clear();
  }
}