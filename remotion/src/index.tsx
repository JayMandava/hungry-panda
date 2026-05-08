/**
 * Remotion entry point for Hungry Panda Reel Renderer
 * Phase 5: Remotion Spike - Alternative renderer behind feature flag
 * 
 * FIXED: Dynamic duration based on editPlan.target_duration
 * No longer hardcoded to 30 seconds - derives from props
 */
import { Composition, registerRoot, calculateMetadata } from "remotion";
import { ReelComposition, REEL_SCHEMA, ReelProps } from "./compositions/ReelComposition";

// Register compositions with dynamic duration
registerRoot(() => {
  return (
    <>
      <Composition
        id="ReelComposition"
        component={ReelComposition}
        durationInFrames={900} // Default for Studio preview (will be overridden by calculateMetadata)
        fps={30}
        width={1080}
        height={1920}
        schema={REEL_SCHEMA}
        defaultProps={{
          editPlan: {
            schema_version: "1.0.0",
            target_duration: 30,
            segments: [],
            global_settings: {
              visual_filter: "none",
              transition_style: "standard",
              output_width: 1080,
              output_height: 1920,
              output_fps: 30
            }
          }
        }}
        calculateMetadata={async ({ props }) => {
          // FIXED: Dynamic duration based on edit plan target_duration
          const targetDuration = props.editPlan?.target_duration ?? 30;
          const fps = props.editPlan?.global_settings?.output_fps ?? 30;
          
          // Calculate frames from target duration
          const durationInFrames = Math.round(targetDuration * fps);
          
          // Ensure minimum 30 seconds for Instagram
          const minFrames = 30 * fps;
          const finalDurationInFrames = Math.max(durationInFrames, minFrames);
          
          console.log(`[Remotion] Dynamic duration: ${targetDuration}s = ${finalDurationInFrames} frames @ ${fps}fps`);
          
          return {
            durationInFrames: finalDurationInFrames,
          };
        }}
      />
    </>
  );
});
