import { AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { createTikTokStyleCaptions, Caption } from "@remotion/captions";
import captions from "./captions.json";

const { pages } = createTikTokStyleCaptions({ captions: captions as Caption[], combineTokensWithinMilliseconds: 900 });

const Page: React.FC<{ page: (typeof pages)[number] }> = ({ page }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = page.startMs + (frame / fps) * 1000;
  const pop = spring({ frame, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 420 }}>
      <div style={{ fontFamily: "DejaVu Sans, sans-serif", fontWeight: 900, fontSize: 92, textAlign: "center",
        width: 950, transform: `scale(${0.85 + 0.15 * pop})`, WebkitTextStroke: "10px black", paintOrder: "stroke" }}>
        {page.tokens.map((tk) => {
          const active = tk.fromMs <= t && t < tk.toMs;
          return <span key={tk.fromMs} style={{ color: active ? "#FFD200" : "white" }}>{tk.text.toUpperCase()}</span>;
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Clip: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      <OffthreadVideo src={staticFile("clip.mp4")} />
      {pages.map((p, i) => {
        const next = pages[i + 1]?.startMs ?? p.startMs + p.durationMs;
        const from = Math.round((p.startMs / 1000) * fps);
        const dur = Math.max(1, Math.round(((next - p.startMs) / 1000) * fps));
        return <Sequence key={i} from={from} durationInFrames={dur}><Page page={p} /></Sequence>;
      })}
    </AbsoluteFill>
  );
};
