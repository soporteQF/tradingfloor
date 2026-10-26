/** Post-processing effects */

import * as THREE from 'three';

/** Scanline shader for CRT effect */
export function createScanlineShader(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      tDiffuse: { value: null },
      opacity: { value: 0.08 },
      scale: { value: 1024 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float opacity;
      uniform float scale;
      varying vec2 vUv;
      void main() {
        vec4 color = texture2D(tDiffuse, vUv);
        // Scanlines
        float scan = sin(vUv.y * scale) * 0.5 + 0.5;
        color.rgb *= mix(1.0, 0.95, opacity * (1.0 - scan));
        gl_FragColor = color;
      }
    `,
  });
}

/** Vignette shader */
export function createVignetteShader(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      tDiffuse: { value: null },
      offset: { value: 0.5 },
      darkness: { value: 0.3 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float offset;
      uniform float darkness;
      varying vec2 vUv;
      void main() {
        vec4 color = texture2D(tDiffuse, vUv);
        vec2 center = vUv - 0.5;
        float dist = length(center) * 2.0;
        float vignette = smoothstep(offset, 1.0, dist);
        color.rgb *= mix(1.0, 1.0 - darkness, vignette);
        gl_FragColor = color;
      }
    `,
  });
}

/** Chromatic aberration shader */
export function createChromaticAberrationShader(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      tDiffuse: { value: null },
      amount: { value: 0.005 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float amount;
      varying vec2 vUv;
      void main() {
        vec2 offset = amount * vec2(1.0, 0.0);
        float r = texture2D(tDiffuse, vUv + offset).r;
        float g = texture2D(tDiffuse, vUv).g;
        float b = texture2D(tDiffuse, vUv - offset).b;
        gl_FragColor = vec4(r, g, b, 1.0);
      }
    `,
  });
}

/** Film grain shader */
export function createFilmGrainShader(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      tDiffuse: { value: null },
      time: { value: 0 },
      intensity: { value: 0.02 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float time;
      uniform float intensity;
      varying vec2 vUv;
      float rand(vec2 co) {
        return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
      }
      void main() {
        vec4 color = texture2D(tDiffuse, vUv);
        float grain = rand(vUv * 100.0 + time) * 2.0 - 1.0;
        color.rgb += grain * intensity;
        gl_FragColor = color;
      }
    `,
  });
}

/** Create all effects for the composer */
export function createEffects(): {
  bloom: any;
  scanlines: any;
  vignette: any;
  chromatic: any;
  grain: any;
} {
  // These are created in FloorScene, exported here for reference
  return {
    bloom: null as any,
    scanlines: null as any,
    vignette: null as any,
    chromatic: null as any,
    grain: null as any,
  };
}