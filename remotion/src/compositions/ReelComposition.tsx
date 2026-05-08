/**
 * ReelComposition - Main Remotion component for rendering Instagram Reels
 * 
 * Phase 5: Remotion Spike - FIXED to match actual edit_plan contract
 * 
 * Real edit_plan structure (from analyzer.py:generate_edit_plan):
 * - plan_schema_version: "1.0.0"
 * - target_duration: number
 * - segments: Array of {
 *     segment_id, asset_id, source_path, media_type, role,
 *     start_time, duration, transition, overlay, effects, ai_planned,
 *     source_metadata: { file_exists, media_type, role, analysis_summary, selection_reason, selection_source }
 *   }
 * - global_settings: { visual_filter, transition_style, output_width, output_height, output_fps, supported_transitions }
 * 
 * Transitions in real plan: "hard_cut", "crossfade", "fade", "fade_in"
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

// FIXED: Real edit plan schema matching analyzer.py output
const SegmentSchema = z.object({
  segment_id: z.string(),
  asset_id: z.string(),
  source_path: z.string(),  // Actual file path (top-level, not in source_metadata)
  media_type: z.enum(["video", "image"]),
  role: z.enum(["intro", "body", "outro"]),
  start_time: z.number().default(0),
  duration: z.number().min(1).max(15),  // Raised to 15s to match planner (images stretchable to 15s)
  transition: z.enum(["hard_cut", "crossfade", "fade", "fade_in"]).default("hard_cut"),
  overlay: z.any().optional(),
  effects: z.any().optional(),
  ai_planned: z.boolean().default(false),
  source_metadata: z.object({
    file_exists: z.boolean(),
    media_type: z.enum(["video", "image"]),
    role: z.enum(["intro", "body", "outro"]),
    analysis_summary: z.object({
      hook_strength: z.number(),
      food_clarity: z.number(),
      motion_quality: z.number(),
      lighting_score: z.number(),
      orientation_fit: z.number(),
      overall_score: z.number()
    }),
    selection_reason: z.string(),
    selection_source: z.string()
  }).optional()
});

// FIXED: Match global_settings from real edit plan
const GlobalSettingsSchema = z.object({
  visual_filter: z.enum(["none", "natural", "warm", "rich", "fresh"]).default("none"),
  transition_style: z.enum(["auto", "cut", "smooth"]).default("auto"),
  output_width: z.number().default(1080),
  output_height: z.number().default(1920),
  output_fps: z.number().default(30),
  supported_transitions: z.array(z.string()).default(["hard_cut", "crossfade", "fade", "fade_in"])
});

const EditPlanSchema = z.object({
  plan_schema_version: z.string().default("1.0.0"),
  target_duration: z.number().min(25).max(65),
  segments: z.array(SegmentSchema),
  global_settings: GlobalSettingsSchema.default({
    visual_filter: "none",
    transition_style: "auto",
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

// FIXED: Map real plan transitions to Remotion transitions
const mapTransition = (planTransition: string): "hard_cut" | "fade" | "dissolve" | "slide" => {
  const transitionMap: Record<string, "hard_cut" | "fade" | "dissolve" | "slide"> = {
    "hard_cut": "hard_cut",
    "crossfade": "fade",
    "fade": "fade",
    "fade_in": "fade"
  };
  return transitionMap[planTransition] || "hard_cut";
};

// Ken Burns effect for images
const KenBurnsImage: React.FC<{
  src: string;
  durationInFrames: number;
  style?: React.CSSProperties;
}> = ({ src, durationInFrames, style }) => {
  const frame = useCurrentFrame();
  
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
  transition: "hard_cut" | "fade" | "dissolve" | "slide";
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

// Individual segment component - FIXED: use source_path and media_type
const Segment: React.FC<{
  segment: z.infer<typeof SegmentSchema>;
  durationInFrames: number;
  isLast: boolean;
}> = ({ segment, durationInFrames, isLast }) => {
  // FIXED: Use source_path from top level, not source_metadata
  const sourcePath = segment.source_path;
  const mediaType = segment.media_type;
  
  // Map transition from plan to Remotion format
  const remotionTransition = mapTransition(segment.transition);
  
  if (mediaType === "video") {
    return (
      <TransitionWrapper
        transition={remotionTransition}
        durationInFrames={durationInFrames}
        isActive={!isLast}
      >
        <Video
          src={staticFile(sourcePath)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover"
          }}
        />
      </TransitionWrapper>
    );
  } else {
    return (
      <TransitionWrapper
        transition={remotionTransition}
        durationInFrames={durationInFrames}
        isActive={!isLast}
      >
        <KenBurnsImage
          src={staticFile(sourcePath)}
          durationInFrames={durationInFrames}
        />
      </TransitionWrapper>
    );
  }
};

// Main composition component - FIXED: use plan_schema_version
export const ReelComposition: React.FC<ReelProps> = ({ editPlan }) => {
  const { fps, durationInFrames } = useVideoConfig();
  
  // FIXED: Validate and parse edit plan with correct schema
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
  
  // Duration is now dynamically set via calculateMetadata in index.tsx
  // based on editPlan.target_duration, validated to meet Instagram 30s minimum
  
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
