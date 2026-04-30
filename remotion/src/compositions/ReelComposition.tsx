/**
 * ReelComposition - Main Remotion component for rendering Instagram Reels
 * 
 * Consumes the same edit_plan contract as the FFmpeg renderer:
 * - schema_version: "1.0.0"
 * - target_duration: number (seconds)
 * - segments: Array of segment objects with role, duration, transition, etc.
 * - global_settings: visual_filter, transition_style, output specs
 * 
 * Phase 5: Remotion Spike
 */
import React, { useMemo } from "react";
import { 
  AbsoluteFill, 
  Sequence, 
  Video, 
  Img, 
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  Easing,
  staticFile
} from "remotion";
import { z } from "zod";

// Edit Plan Schema (matches Phase 3 contract)
const SegmentSchema = z.object({
  asset_index: z.number(),
  role: z.enum(["intro", "body", "outro"]),
  duration: z.number().min(1).max(10),
  transition: z.enum(["hard_cut", "fade", "dissolve", "slide"]).default("hard_cut"),
  source_metadata: z.object({
    type: z.enum(["video", "image"]),
    path: z.string(),
    original_duration: z.number().optional(),
    orientation: z.enum(["vertical", "horizontal", "square"]).optional(),
    content_hash: z.string().optional()
  })
});

const GlobalSettingsSchema = z.object({
  visual_filter: z.enum(["none", "natural", "warm", "rich", "fresh"]).default("none"),
  transition_style: z.enum(["standard", "minimal", "dynamic"]).default("standard"),
  output_width: z.number().default(1080),
  output_height: z.number().default(1920),
  output_fps: z.number().default(30)
});

const EditPlanSchema = z.object({
  schema_version: z.string().default("1.0.0"),
  target_duration: z.number().min(25).max(65),
  segments: z.array(SegmentSchema),
  global_settings: GlobalSettingsSchema.default({
    visual_filter: "none",
    transition_style: "standard",
    output_width: 1080,
    output_height: 1920,
    output_fps: 30
  })
});

export const REEL_SCHEMA = z.object({
  editPlan: EditPlanSchema
});

export type ReelProps = z.infer<typeof REEL_SCHEMA>;

// Visual filter CSS presets (matching FFmpeg presets)
const VISUAL_FILTERS: Record<string, React.CSSProperties> = {
  none: {},
  natural: {
    filter: "contrast(1.0) saturate(1.0) brightness(1.0)"
  },
  warm: {
    filter: "contrast(1.05) saturate(1.1) brightness(1.02) sepia(0.1)"
  },
  rich: {
    filter: "contrast(1.15) saturate(1.2) brightness(0.98)"
  },
  fresh: {
    filter: "contrast(1.0) saturate(1.15) brightness(1.03)"
  }
};

// Ken Burns effect for images
const KenBurnsImage: React.FC<{
  src: string;
  durationInFrames: number;
  style?: React.CSSProperties;
}> = ({ src, durationInFrames, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  // Slow zoom from 1.0 to 1.1 over the duration
  const scale = interpolate(
    frame,
    [0, durationInFrames],
    [1, 1.1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.linear
    }
  );
  
  // Subtle pan from center to slightly offset
  const x = interpolate(
    frame,
    [0, durationInFrames],
    [0, -20],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.linear
    }
  );
  
  const y = interpolate(
    frame,
    [0, durationInFrames],
    [0, -10],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.linear
    }
  );
  
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${x}px, ${y}px)`,
          ...style
        }}
      />
    </AbsoluteFill>
  );
};

// Transition wrapper component
const TransitionWrapper: React.FC<{
  children: React.ReactNode;
  transition: string;
  durationInFrames: number;
  isActive: boolean;
}> = ({ children, transition, durationInFrames, isActive }) => {
  const frame = useCurrentFrame();
  
  if (!isActive || transition === "hard_cut") {
    return <>{children}</>;
  }
  
  let opacity = 1;
  let transform = "translateX(0)";
  
  if (transition === "fade" || transition === "dissolve") {
    // Fade in at start, fade out at end
    const fadeInDuration = Math.min(15, durationInFrames / 4);
    const fadeOutDuration = Math.min(15, durationInFrames / 4);
    const fadeOutStart = durationInFrames - fadeOutDuration;
    
    if (frame < fadeInDuration) {
      opacity = interpolate(frame, [0, fadeInDuration], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp"
      });
    } else if (frame > fadeOutStart) {
      opacity = interpolate(frame, [fadeOutStart, durationInFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp"
      });
    }
  } else if (transition === "slide") {
    // Slide in from right
    const slideDuration = Math.min(20, durationInFrames / 3);
    
    if (frame < slideDuration) {
      const x = interpolate(frame, [0, slideDuration], [100, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.ease)
      });
      transform = `translateX(${x}%)`;
    }
  }
  
  return (
    <div style={{ opacity, transform, width: "100%", height: "100%" }}>
      {children}
    </div>
  );
};

// Individual segment component
const Segment: React.FC<{
  segment: z.infer<typeof SegmentSchema>;
  durationInFrames: number;
  isLast: boolean;
}> = ({ segment, durationInFrames, isLast }) => {
  const { type, path } = segment.source_metadata;
  const visualFilter = VISUAL_FILTERS["none"]; // Would come from global_settings
  
  if (type === "video") {
    return (
      <TransitionWrapper
        transition={segment.transition}
        durationInFrames={durationInFrames}
        isActive={!isLast}
      >
        <Video
          src={staticFile(path)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            ...visualFilter
          }}
        />
      </TransitionWrapper>
    );
  } else {
    return (
      <TransitionWrapper
        transition={segment.transition}
        durationInFrames={durationInFrames}
        isActive={!isLast}
      >
        <KenBurnsImage
          src={staticFile(path)}
          durationInFrames={durationInFrames}
          style={visualFilter}
        />
      </TransitionWrapper>
    );
  }
};

// Main composition component
export const ReelComposition: React.FC<ReelProps> = ({ editPlan }) => {
  const { fps, durationInFrames } = useVideoConfig();
  
  // Validate and parse edit plan
  const parsedPlan = useMemo(() => {
    try {
      return EditPlanSchema.parse(editPlan);
    } catch (error) {
      console.error("Invalid edit plan:", error);
      return null;
    }
  }, [editPlan]);
  
  if (!parsedPlan) {
    return (
      <AbsoluteFill
        style={{
          backgroundColor: "#000",
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}
      >
        <div style={{ color: "#fff", fontSize: 24 }}>Invalid Edit Plan</div>
      </AbsoluteFill>
    );
  }
  
  const { segments, global_settings, target_duration } = parsedPlan;
  const visualFilter = VISUAL_FILTERS[global_settings.visual_filter] || VISUAL_FILTERS.none;
  
  // Calculate frame positions for each segment
  let currentFrame = 0;
  const segmentPositions = segments.map((segment) => {
    const segmentFrames = Math.round(segment.duration * fps);
    const startFrame = currentFrame;
    currentFrame += segmentFrames;
    
    return {
      segment,
      startFrame,
      durationInFrames: segmentFrames
    };
  });
  
  // Ensure we meet minimum duration requirement (Instagram needs 30s minimum)
  const minFrames = 30 * fps;
  const actualFrames = Math.max(durationInFrames, minFrames);
  
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {segmentPositions.map(({ segment, startFrame, durationInFrames: segmentFrames }, index) => (
        <Sequence
          key={index}
          from={startFrame}
          durationInFrames={segmentFrames}
        >
          <Segment
            segment={segment}
            durationInFrames={segmentFrames}
            isLast={index === segments.length - 1}
          />
        </Sequence>
      ))}
      
      {/* Global visual filter overlay */}
      {global_settings.visual_filter !== "none" && (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            ...visualFilter
          }}
        />
      )}
      
      {/* Duration indicator (debug) */}
      {process.env.NODE_ENV === "development" && (
        <div
          style={{
            position: "absolute",
            bottom: 20,
            left: 20,
            color: "#fff",
            fontSize: 14,
            fontFamily: "monospace",
            backgroundColor: "rgba(0,0,0,0.7)",
            padding: "8px 12px",
            borderRadius: 4
          }}
        >
          Target: {target_duration}s | Segments: {segments.length} | Filter: {global_settings.visual_filter}
        </div>
      )}
    </AbsoluteFill>
  );
};
