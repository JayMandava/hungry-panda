# Remotion Renderer - Phase 5 Spike

Alternative renderer for Instagram Reels using [Remotion](https://www.remotion.dev/) - a React-based video creation framework.

## Overview

This is an experimental renderer that consumes the same `edit_plan` contract as the FFmpeg renderer. It can be enabled via feature flag for gradual rollout.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   reels.py API  │────▶│  Feature Flag   │────▶│ FFmpegRenderer  │
│                 │     │   (switcher)    │     │   (default)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼ (if enabled)
                        ┌─────────────────┐
                        │ RemotionRenderer│
                        │   (Node.js CLI) │
                        └─────────────────┘
```

## Setup

1. **Install Node.js 18+** and npm

2. **Install Remotion dependencies:**
   ```bash
   cd remotion
   npm install
   ```

3. **Enable the feature flag:**
   ```bash
   export ENABLE_REMOTION_RENDERER=true
   ```

## Usage

### Feature Flag Control

```python
from infra.config.feature_flags import is_remotion_enabled

if is_remotion_enabled():
    # Use Remotion
    renderer = RemotionRenderer()
else:
    # Use FFmpeg (default)
    renderer = FFmpegRenderer()
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_REMOTION_RENDERER` | `false` | Enable Remotion instead of FFmpeg |
| `REMOTION_OUTPUT_DIR` | `./remotion_output` | Directory for Remotion outputs |

## Edit Plan Contract

Remotion consumes the same Phase 3 schema:

```typescript
interface EditPlan {
  schema_version: "1.0.0";
  target_duration: number;  // 25-65 seconds
  segments: Array<{
    asset_index: number;
    role: "intro" | "body" | "outro";
    duration: number;  // 1-10 seconds per segment
    transition: "hard_cut" | "fade" | "dissolve" | "slide";
    source_metadata: {
      type: "video" | "image";
      path: string;
    };
  }>;
  global_settings: {
    visual_filter: "none" | "natural" | "warm" | "rich" | "fresh";
    transition_style: "standard" | "minimal" | "dynamic";
  };
}
```

## Components

### ReelComposition
Main Remotion component that renders the reel:
- Handles video clips with trim/scale
- Applies Ken Burns effect to images
- Supports transitions (fade, slide, hard cut)
- Applies visual filters via CSS
- Meets Instagram specs (1080x1920, 30fps, H.264)

## Development

### Run Remotion Studio (preview/debug)
```bash
cd remotion
npm run start
```

### Manual render test
```bash
cd remotion
npm run render -- --props=./public/test-plan.json
```

## Comparison: FFmpeg vs Remotion

| Feature | FFmpeg | Remotion |
|---------|--------|----------|
| **Speed** | Faster (native) | Slower (browser-based) |
| **Flexibility** | Limited | High (React components) |
| **Preview** | None | Studio + Player |
| **Text/Overlays** | Complex | Easy (React) |
| **Deployment** | Single binary | Node.js + npm deps |
| **Maintenance** | Stable | Active development |

## Known Limitations

1. **Requires Node.js runtime** - adds deployment complexity
2. **Slower rendering** - browser-based vs native ffmpeg
3. **Memory usage** - Chrome headless can be memory-intensive
4. **npm dependencies** - ~500MB node_modules

## Future Work (Work Item 11)

Evaluate Remotion Player for interactive preview UI:
- Real-time scrubbing through edit plan
- Visual timeline representation
- Pre-render preview before full export
- Client-side rendering option

## References

- [Remotion Docs](https://www.remotion.dev/docs/)
- [Remotion Player](https://www.remotion.dev/docs/player/)
- [FFmpeg Renderer](../workers/reels/renderer.py) - baseline comparison
