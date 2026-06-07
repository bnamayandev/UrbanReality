/**
 * Building3DView — dumb display component.
 * Receives an already-generated image and/or GLB URL.
 * No fetching, no 3D-generation triggering — that all lives in ImageConfirmModal + App.
 */
import { Download } from 'lucide-react'

export function Building3DView({ imageSrc, glbUrl, style }) {
  if (!imageSrc && !glbUrl) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, ...style }}>
      {/* 2D image thumbnail */}
      {imageSrc && (
        <div style={{
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          overflow: 'hidden',
          background: '#0a0a0f',
        }}>
          <img
            src={imageSrc}
            alt="Generated building"
            style={{ width: '100%', display: 'block', objectFit: 'contain', maxHeight: 180 }}
          />
        </div>
      )}

      {/* 3D model viewer */}
      {glbUrl && (
        <div style={{
          border: '1px solid rgba(0,212,255,0.3)',
          borderRadius: 'var(--radius)',
          overflow: 'hidden',
          background: 'var(--bg-3)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '7px 10px', borderBottom: '1px solid var(--border)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--cyan)', fontWeight: 600 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 5px var(--cyan)' }} />
              3D Model
            </div>
            <a
              href={glbUrl}
              download
              style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-2)', textDecoration: 'none' }}
            >
              <Download size={12} />
              Download GLB
            </a>
          </div>
          {/* Image-based lighting: SF3D bakes full PBR materials (albedo/
              roughness/metallic/normal); without an environment map the
              metallic/roughness channels have nothing to reflect and the model
              looks flat. An outdoor urban HDR lights it like a real building.
              Skybox is left off so the dark UI shows through. */}
          <model-viewer
            src={glbUrl}
            alt="3D building model"
            camera-controls
            auto-rotate
            environment-image="/hdri/urban_alley_01_1k.hdr"
            tone-mapping="aces"
            exposure="1.0"
            shadow-intensity="1"
            shadow-softness="0.7"
            style={{ width: '100%', height: '260px', background: 'transparent' }}
          />
        </div>
      )}
    </div>
  )
}
