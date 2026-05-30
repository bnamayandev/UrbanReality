import { useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';

// Visual config per building type: how wide/deep relative to footprint
const TYPE_CONFIG = {
  'Residential (High-rise)': { wRatio: 0.40, dRatio: 0.40, hasPodium: false },
  'Residential (Mid-rise)':  { wRatio: 0.60, dRatio: 0.50, hasPodium: false },
  'Mixed-Use':               { wRatio: 0.65, dRatio: 0.60, hasPodium: true  },
  'Commercial Office':       { wRatio: 0.55, dRatio: 0.55, hasPodium: false },
  'Retail / Podium':         { wRatio: 0.80, dRatio: 0.70, hasPodium: true  },
};

// Body color and window glass tint per material
const MATERIAL_PALETTE = {
  'Concrete & Glass': { body: 0x8bafc9, glass: 0x5b8fa8, shine: 60 },
  'Mass Timber':      { body: 0xb5865a, glass: 0x6a9966, shine: 20 },
  'Steel Frame':      { body: 0x8899aa, glass: 0x4a7a9b, shine: 90 },
  'Brick & Concrete': { body: 0xb87355, glass: 0x8a9ba8, shine: 15 },
};

/**
 * Renders an isolated 3D building on a clean background.
 *
 * Props:
 *   floors      — number of floors (drives height)
 *   footprintM2 — footprint area in m² (drives width/depth)
 *   type        — building type string matching the builder dropdown
 *   material    — material string matching the builder dropdown
 *   width       — canvas width in px (default 280)
 *   height      — canvas height in px (default 280)
 *   spin        — whether the building slowly rotates (default true)
 *   onReady     — optional callback(dataURL: string) fired after first render
 */
export function BuildingPreview({
  floors = 24,
  footprintM2 = 2000,
  type = 'Residential (High-rise)',
  material = 'Concrete & Glass',
  width = 280,
  height = 280,
  spin = true,
  onReady = null,
}) {
  const mountRef   = useRef(null);
  const rendererRef = useRef(null);
  const frameRef   = useRef(null);
  const sceneRef   = useRef(null);
  const cameraRef  = useRef(null);

  // Rebuild scene whenever building parameters change
  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    // ── Scene ──────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1b2e); // matches app dark theme
    sceneRef.current = scene;

    // ── Camera ─────────────────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    camera.position.set(5.5, 6, 7.5);
    camera.lookAt(0, 2.5, 0);
    cameraRef.current = camera;

    // ── Renderer ───────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;
    el.appendChild(renderer.domElement);

    // ── Lighting ───────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x8ca0c0, 0.75));

    const sun = new THREE.DirectionalLight(0xfff5e0, 1.5);
    sun.position.set(8, 14, 6);
    sun.castShadow = true;
    Object.assign(sun.shadow.camera, { near: 0.1, far: 50, left: -10, right: 10, top: 12, bottom: -10 });
    sun.shadow.mapSize.set(1024, 1024);
    scene.add(sun);

    // Soft blue fill from the opposite side
    const fill = new THREE.DirectionalLight(0x4060a0, 0.35);
    fill.position.set(-6, 4, -4);
    scene.add(fill);

    // ── Ground + grid ──────────────────────────────────────────────────────
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 22),
      new THREE.MeshLambertMaterial({ color: 0x0a1628 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const grid = new THREE.GridHelper(18, 18, 0x1e3a5f, 0x162039);
    grid.position.y = 0.005;
    scene.add(grid);

    // ── Building geometry ──────────────────────────────────────────────────
    const cfg     = TYPE_CONFIG[type]     ?? TYPE_CONFIG['Residential (High-rise)'];
    const palette = MATERIAL_PALETTE[material] ?? MATERIAL_PALETTE['Concrete & Glass'];

    const sideLen = Math.sqrt(footprintM2) * 0.007; // m → scene units
    const bW = sideLen * cfg.wRatio * 2;
    const bD = sideLen * cfg.dRatio * 2;
    const bH = floors * 0.14;

    const winTex = buildWindowTexture(bW, bH, palette);

    const towerMat = new THREE.MeshPhongMaterial({
      color: palette.body,
      map: winTex,
      shininess: palette.shine,
      specular: new THREE.Color(0x334455),
    });

    const tower = new THREE.Mesh(new THREE.BoxGeometry(bW, bH, bD), towerMat);
    tower.position.y = bH / 2;
    tower.castShadow = true;
    tower.receiveShadow = true;
    scene.add(tower);

    // Mechanical penthouse on roof
    const penthouseH = Math.min(bH * 0.06, 0.4);
    const penthouse = new THREE.Mesh(
      new THREE.BoxGeometry(bW * 0.35, penthouseH, bD * 0.35),
      new THREE.MeshPhongMaterial({ color: 0x2a3d55 }),
    );
    penthouse.position.y = bH + penthouseH / 2;
    penthouse.castShadow = true;
    scene.add(penthouse);

    // Podium for mixed-use / retail types
    if (cfg.hasPodium) {
      const podH = Math.min(bH * 0.18, 0.7);
      const podium = new THREE.Mesh(
        new THREE.BoxGeometry(bW * 1.35, podH, bD * 1.35),
        new THREE.MeshPhongMaterial({ color: palette.body, shininess: 15 }),
      );
      podium.position.y = podH / 2;
      podium.castShadow = true;
      podium.receiveShadow = true;
      scene.add(podium);
    }

    // ── Animate ────────────────────────────────────────────────────────────
    let tick = 0;
    let notifiedReady = false;

    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      if (spin) tower.rotation.y = tick * 0.005;
      tick++;
      renderer.render(scene, camera);

      // Fire onReady with the first completed frame as a PNG data URL
      if (!notifiedReady && onReady) {
        notifiedReady = true;
        onReady(renderer.domElement.toDataURL('image/png'));
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(frameRef.current);
      renderer.dispose();
      winTex.dispose();
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, [floors, footprintM2, type, material, width, height, spin, onReady]);

  /**
   * Capture the current frame as a PNG data URL.
   * Call this from a parent ref to grab the image before placement.
   */
  const captureImage = useCallback(() => {
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) return null;
    rendererRef.current.render(sceneRef.current, cameraRef.current);
    return rendererRef.current.domElement.toDataURL('image/png');
  }, []);

  // Expose captureImage via the DOM node so parents can call mountRef.current.capture()
  useEffect(() => {
    if (mountRef.current) mountRef.current.capture = captureImage;
  }, [captureImage]);

  return (
    <div
      ref={mountRef}
      style={{
        width,
        height,
        borderRadius: 8,
        overflow: 'hidden',
        background: '#0d1b2e',
        flexShrink: 0,
      }}
    />
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Generates a canvas texture that simulates a building facade with window grids.
 * Lit windows are brighter; unlit windows are dim — gives a realistic night-time look.
 */
function buildWindowTexture(bW, bH, palette) {
  const PX_PER_UNIT = 40;
  const tw = Math.max(Math.round(bW * PX_PER_UNIT), 64);
  const th = Math.max(Math.round(bH * PX_PER_UNIT), 128);

  const canvas = document.createElement('canvas');
  canvas.width  = tw;
  canvas.height = th;
  const ctx = canvas.getContext('2d');

  // Facade base
  const bodyHex = '#' + palette.body.toString(16).padStart(6, '0');
  ctx.fillStyle = bodyHex;
  ctx.fillRect(0, 0, tw, th);

  // Window grid
  const cols    = Math.max(3, Math.floor(bW * 7));
  const rows    = Math.max(4, Math.floor(bH * 7));
  const padFrac = 0.08;
  const cellW   = tw / cols;
  const cellH   = th / rows;
  const winW    = cellW * (1 - padFrac * 2);
  const winH    = cellH * (1 - padFrac * 2.5);

  const gr = (palette.glass >> 16) & 0xff;
  const gg = (palette.glass >> 8)  & 0xff;
  const gb =  palette.glass        & 0xff;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const lit   = Math.random() > 0.28;
      const alpha = lit ? 0.9 : 0.18;
      ctx.fillStyle = `rgba(${gr},${gg},${gb},${alpha})`;
      ctx.fillRect(
        c * cellW + cellW * padFrac,
        r * cellH + cellH * padFrac,
        winW,
        winH,
      );
    }
  }

  return new THREE.CanvasTexture(canvas);
}
