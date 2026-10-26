/** Entry point for Three.js Floor */

import * as THREE from 'three';
import { FloorScene } from './scene/FloorScene.js';
import { OverlayManager } from './ui/OverlayManager.js';

// Global references for inline handlers
declare global {
  interface Window {
    floorScene: FloorScene;
    overlayManager: OverlayManager;
    cameraController: any;
  }
}

async function main(): Promise<void> {
  try {
    // Create overlay manager first (handles loading screen)
    const overlayManager = new OverlayManager();
    window.overlayManager = overlayManager;

    // Get canvas
    const canvas = document.createElement('canvas');
    canvas.id = 'three-canvas';
    document.getElementById('app')!.appendChild(canvas);

    // Create floor scene
    const floorScene = new FloorScene({
      canvas,
      onStatusUpdate: (status) => overlayManager.updateFromStatus(status),
      onError: (error) => {
        console.error('FloorScene error:', error);
        const loading = document.getElementById('loading');
        const loadStatus = document.getElementById('loadStatus');
        const loadError = document.getElementById('loadError');
        if (loading) loading.style.display = 'flex';
        if (loadStatus) loadStatus.textContent = 'Error inicializando escena';
        if (document.getElementById('loadError')) {
          document.getElementById('loadError')!.textContent = error.message;
          document.getElementById('loadError')!.style.display = 'block';
        }
      },
      reducedMotion: false,
    });
    window.floorScene = floorScene;

    // Expose camera controller for UI
    window.cameraController = floorScene.getCameraController();

    // Wire overlay manager callbacks
    window.overlayManager.setCommandCallback(async (type: string, data: any) => {
      await window.floorScene.sendCommand(type, data);
    });

    // Global event handlers for UI
    window.addEventListener('reduced-motion', (e: CustomEvent) => {
      window.floorScene.setReducedMotion(e.detail.enabled);
    });

    window.addEventListener('focus-chief', () => {
      window.floorScene.getCameraController().focusOnChief({
        x: 0, y: 0, z: 0 // Will be updated by camera controller
      });
    });

    // Keyboard shortcuts
    window.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;

      switch (e.key.toLowerCase()) {
        case 'm':
          window.overlayManager?.toggleMinimap?.();
          break;
        case 'r':
          window.overlayManager?.toggleReducedMotion?.();
          break;
        case ' ':
          e.preventDefault();
          window.floorScene.getCameraController().focusOnChief({ x: 0, y: 0, z: 0 });
          break;
      }
    });

    // Window resize
    window.addEventListener('resize', () => {
      window.floorScene.resize(window.innerWidth, window.innerHeight);
    });

    // Cleanup on unload
    window.addEventListener('beforeunload', () => {
      window.floorScene.dispose();
    });

    // Expose for debugging
    (window as any).THREE = await import('three');
    (window as any).floorScene = window.floorScene;

    console.log('🚀 NEXUS QUANT FLOOR ready');
  } catch (error) {
    console.error('Failed to initialize:', error);
    const loading = document.getElementById('loading');
    const loadStatus = document.getElementById('loadStatus');
    const loadError = document.getElementById('loadError');
    if (loading) loading.style.display = 'flex';
    if (document.getElementById('loadStatus')) document.getElementById('loadStatus')!.textContent = 'Error crítico';
    if (document.getElementById('loadError')) {
      document.getElementById('loadError')!.textContent = error instanceof Error ? error.message : String(error);
      document.getElementById('loadError')!.style.display = 'block';
    }
  }
}

// Start
main().catch(console.error);