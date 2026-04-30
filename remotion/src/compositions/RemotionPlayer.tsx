/**
 * RemotionPlayer - Interactive preview component for reel editing
 * 
 * Phase 5 Work Item 11: Evaluate Remotion Player for Preview UI
 * 
 * This component demonstrates how Remotion Player could power an interactive
 * preview/timeline UI for the reel editor. Unlike the static render endpoint,
 * this allows real-time scrubbing and visual feedback before final export.
 * 
 * Usage: This would be integrated into the frontend for interactive preview.
 */
import React, { useState, useRef, useCallback } from "react";
import { Player, PlayerRef } from "@remotion/player";
import { ReelComposition, REEL_SCHEMA } from "./ReelComposition";
import { z } from "zod";

interface RemotionPlayerProps {
  editPlan: z.infer<typeof REEL_SCHEMA>["editPlan"];
  onTimeUpdate?: (frame: number, timeInSeconds: number) => void;
  onPlay?: () => void;
  onPause?: () => void;
  onEnded?: () => void;
}

/**
 * RemotionPlayerPreview - Interactive reel preview component
 * 
 * Features:
 * - Real-time scrubbing through the timeline
 * - Visual feedback on segment boundaries
 * - Current position indicator
 * - Play/pause controls
 * - Frame-accurate preview (what you see is what you get)
 */
export const RemotionPlayerPreview: React.FC<RemotionPlayerProps> = ({
  editPlan,
  onTimeUpdate,
  onPlay,
  onPause,
  onEnded
}) => {
  const playerRef = useRef<PlayerRef>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  
  const fps = 30;
  const durationInFrames = Math.round(editPlan.target_duration * fps);
  
  // Calculate segment boundaries for visual markers
  const segmentBoundaries = React.useMemo(() => {
    let frame = 0;
    return editPlan.segments.map((segment, index) => {
      const startFrame = frame;
      const segmentFrames = Math.round(segment.duration * fps);
      frame += segmentFrames;
      return {
        index,
        role: segment.role,
        startFrame,
        endFrame: frame - 1,
        startTime: startFrame / fps,
        endTime: (frame - 1) / fps
      };
    });
  }, [editPlan, fps]);
  
  // Determine which segment is currently active
  const currentSegment = segmentBoundaries.find(
    seg => currentFrame >= seg.startFrame && currentFrame <= seg.endFrame
  );
  
  const handleFrameUpdate = useCallback((frame: number) => {
    setCurrentFrame(frame);
    if (onTimeUpdate) {
      onTimeUpdate(frame, frame / fps);
    }
  }, [fps, onTimeUpdate]);
  
  const handlePlay = useCallback(() => {
    setIsPlaying(true);
    onPlay?.();
  }, [onPlay]);
  
  const handlePause = useCallback(() => {
    setIsPlaying(false);
    onPause?.();
  }, [onPause]);
  
  const handleEnded = useCallback(() => {
    setIsPlaying(false);
    onEnded?.();
  }, [onEnded]);
  
  // Jump to specific segment
  const jumpToSegment = (segmentIndex: number) => {
    const segment = segmentBoundaries[segmentIndex];
    if (segment && playerRef.current) {
      playerRef.current.seekTo(segment.startFrame);
    }
  };
  
  return (
    <div style={styles.container}>
      {/* Main Player */}
      <div style={styles.playerWrapper}>
        <Player
          ref={playerRef}
          component={ReelComposition}
          inputProps={{ editPlan }}
          durationInFrames={durationInFrames}
          fps={fps}
          compositionWidth={1080}
          compositionHeight={1920}
          style={{
            width: "100%",
            height: "auto",
            aspectRatio: "9/16"
          }}
          controls
          showVolumeIcon
          allowFullscreen
          clickToPlay
          spaceKeyToPlayOrPause
          onFrameUpdate={handleFrameUpdate}
          onPlay={handlePlay}
          onPause={handlePause}
          onEnded={handleEnded}
          renderLoading={() => (
            <div style={styles.loading}>
              Loading preview...
            </div>
          )}
          errorFallback={({ error }) => (
            <div style={styles.error}>
              Preview Error: {error.message}
            </div>
          )}
        />
      </div>
      
      {/* Segment Timeline */}
      <div style={styles.timeline}>
        <div style={styles.timelineTrack}>
          {segmentBoundaries.map((seg, idx) => (
            <div
              key={idx}
              style={{
                ...styles.segment,
                left: `${(seg.startFrame / durationInFrames) * 100}%`,
                width: `${((seg.endFrame - seg.startFrame + 1) / durationInFrames) * 100}%`,
                backgroundColor: getRoleColor(seg.role),
                border: currentSegment?.index === idx ? "2px solid #fff" : "none"
              }}
              onClick={() => jumpToSegment(idx)}
              title={`${seg.role} (${seg.startTime.toFixed(1)}s - ${seg.endTime.toFixed(1)}s)`}
            >
              <span style={styles.segmentLabel}>{seg.role}</span>
            </div>
          ))}
          
          {/* Playhead */}
          <div
            style={{
              ...styles.playhead,
              left: `${(currentFrame / durationInFrames) * 100}%`
            }}
          />
        </div>
        
        {/* Time Display */}
        <div style={styles.timeDisplay}>
          {formatTime(currentFrame / fps)} / {formatTime(durationInFrames / fps)}
          {currentSegment && (
            <span style={styles.segmentInfo}>
              ({currentSegment.role})
            </span>
          )}
        </div>
      </div>
      
      {/* Segment Navigation */}
      <div style={styles.segmentNav}>
        {editPlan.segments.map((seg, idx) => (
          <button
            key={idx}
            style={{
              ...styles.segmentButton,
              backgroundColor: getRoleColor(seg.role),
              opacity: currentSegment?.index === idx ? 1 : 0.6
            }}
            onClick={() => jumpToSegment(idx)}
          >
            {seg.role} {idx + 1}
          </button>
        ))}
      </div>
      
      {/* Playback Controls */}
      <div style={styles.controls}>
        <button
          style={styles.controlButton}
          onClick={() => playerRef.current?.seekTo(0)}
        >
          ⏮ First
        </button>
        <button
          style={styles.controlButton}
          onClick={() => playerRef.current?.seekTo(Math.max(0, currentFrame - 30))}
        >
          -1s
        </button>
        <button
          style={{ ...styles.controlButton, ...styles.playButton }}
          onClick={() => isPlaying ? playerRef.current?.pause() : playerRef.current?.play()}
        >
          {isPlaying ? "⏸ Pause" : "▶ Play"}
        </button>
        <button
          style={styles.controlButton}
          onClick={() => playerRef.current?.seekTo(Math.min(durationInFrames, currentFrame + 30))}
        >
          +1s
        </button>
        <button
          style={styles.controlButton}
          onClick={() => playerRef.current?.seekTo(durationInFrames)}
        >
          Last ⏭
        </button>
      </div>
    </div>
  );
};

// Helper functions
function getRoleColor(role: string): string {
  switch (role) {
    case "intro": return "#4CAF50";  // Green
    case "outro": return "#F44336"; // Red
    case "body": return "#2196F3";  // Blue
    default: return "#9E9E9E";        // Gray
  }
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const frames = Math.floor((seconds % 1) * 30);
  return `${mins}:${secs.toString().padStart(2, '0')}.${frames.toString().padStart(2, '0')}`;
}

// Styles
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    padding: "16px",
    backgroundColor: "#1a1a1a",
    borderRadius: "8px"
  },
  playerWrapper: {
    position: "relative",
    width: "100%",
    maxWidth: "400px",
    margin: "0 auto",
    backgroundColor: "#000",
    borderRadius: "4px",
    overflow: "hidden"
  },
  loading: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    height: "100%",
    color: "#fff",
    fontSize: "16px"
  },
  error: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    height: "100%",
    color: "#ff4444",
    fontSize: "14px",
    padding: "16px",
    textAlign: "center"
  },
  timeline: {
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },
  timelineTrack: {
    position: "relative",
    height: "32px",
    backgroundColor: "#333",
    borderRadius: "4px",
    overflow: "hidden"
  },
  segment: {
    position: "absolute",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "opacity 0.2s",
    fontSize: "10px",
    color: "#fff",
    textTransform: "uppercase"
  },
  segmentLabel: {
    fontSize: "9px",
    fontWeight: "bold",
    textShadow: "0 1px 2px rgba(0,0,0,0.8)"
  },
  playhead: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: "2px",
    backgroundColor: "#fff",
    transform: "translateX(-50%)",
    zIndex: 10,
    pointerEvents: "none"
  },
  timeDisplay: {
    fontFamily: "monospace",
    fontSize: "14px",
    color: "#fff",
    textAlign: "center"
  },
  segmentInfo: {
    marginLeft: "8px",
    color: "#aaa"
  },
  segmentNav: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
    justifyContent: "center"
  },
  segmentButton: {
    padding: "6px 12px",
    border: "none",
    borderRadius: "4px",
    color: "#fff",
    fontSize: "12px",
    cursor: "pointer",
    transition: "opacity 0.2s"
  },
  controls: {
    display: "flex",
    gap: "8px",
    justifyContent: "center"
  },
  controlButton: {
    padding: "8px 16px",
    backgroundColor: "#333",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px"
  },
  playButton: {
    backgroundColor: "#2196F3",
    fontWeight: "bold"
  }
};

// Example usage component for documentation
export const RemotionPlayerExample: React.FC = () => {
  const examplePlan = {
    schema_version: "1.0.0" as const,
    target_duration: 30,
    segments: [
      {
        asset_index: 0,
        role: "intro" as const,
        duration: 3,
        transition: "fade" as const,
        source_metadata: {
          type: "image" as const,
          path: "example1.jpg"
        }
      },
      {
        asset_index: 1,
        role: "body" as const,
        duration: 5,
        transition: "slide" as const,
        source_metadata: {
          type: "video" as const,
          path: "example2.mp4"
        }
      },
      {
        asset_index: 2,
        role: "body" as const,
        duration: 4,
        transition: "fade" as const,
        source_metadata: {
          type: "image" as const,
          path: "example3.jpg"
        }
      },
      {
        asset_index: 3,
        role: "outro" as const,
        duration: 3,
        transition: "hard_cut" as const,
        source_metadata: {
          type: "image" as const,
          path: "example4.jpg"
        }
      }
    ],
    global_settings: {
      visual_filter: "warm" as const,
      transition_style: "standard" as const,
      output_width: 1080,
      output_height: 1920,
      output_fps: 30
    }
  };
  
  return (
    <div style={{ padding: "20px" }}>
      <h2 style={{ color: "#fff" }}>Remotion Player Preview (Evaluation)</h2>
      <RemotionPlayerPreview
        editPlan={examplePlan}
        onTimeUpdate={(frame, time) => {
          console.log(`Frame: ${frame}, Time: ${time.toFixed(2)}s`);
        }}
      />
    </div>
  );
};
