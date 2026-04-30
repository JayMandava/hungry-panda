/**
 * Remotion entry point for Hungry Panda Reel Renderer
 * Phase 5: Remotion Spike - Alternative renderer behind feature flag
 */
import { Composition, registerRoot } from "remotion";
import { ReelComposition, REEL_SCHEMA, ReelProps } from "./compositions/ReelComposition";

// Register compositions
registerRoot(() => {
  return (
    <>
      <Composition
        id="ReelComposition"
        component={ReelComposition}
        durationInFrames={900} // 30 seconds at 30fps (default)
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
      />
    </>
  );
});
