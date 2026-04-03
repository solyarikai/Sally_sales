/**
 * OnSocial Analytics — Remotion Video Component
 * Format: 1080x1920 (Reels / TikTok / Shorts)
 *
 * Usage in your Remotion project:
 *
 * // Root.tsx
 * import { Composition } from "remotion";
 * import { OnSocialAnalytics } from "./OnSocialAnalytics";
 *
 * export const RemotionRoot = () => (
 *   <Composition
 *     id="OnSocialAnalytics"
 *     component={OnSocialAnalytics}
 *     durationInFrames={600}   // 20 seconds at 30fps
 *     fps={30}
 *     width={1080}
 *     height={1920}
 *   />
 * );
 */

import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";

// ============================================================
// COLOR PALETTE & DESIGN TOKENS
// ============================================================
const COLORS = {
  primary: "#2B7A78",
  primaryLight: "#3AAFA9",
  accent: "#5DB4D8",
  dark: "#17252A",
  darkNav: "#1B4D4A",
  bg: "#F7FAFA",
  white: "#FFFFFF",
  text: "#1A1A2E",
  textLight: "#6B7280",
  red: "#E85D75",
  green: "#22C55E",
  cardShadow: "0 4px 24px rgba(43,122,120,0.10)",
  gradientTeal: "linear-gradient(135deg, #2B7A78 0%, #3AAFA9 100%)",
};

// ============================================================
// ANIMATION HELPERS
// ============================================================
const fadeIn = (frame, startFrame, duration = 15) =>
  interpolate(frame, [startFrame, startFrame + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const slideUp = (frame, startFrame, distance = 60, duration = 18) =>
  interpolate(frame, [startFrame, startFrame + duration], [distance, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const scaleIn = (frame, fps, delay = 0) =>
  spring({ frame: frame - delay, fps, config: { damping: 120, stiffness: 200 } });

// ============================================================
// SUB-COMPONENTS
// ============================================================

// --- Animated Wrapper ---
const FadeSlide = ({ children, delay = 0, style = {} }) => {
  const frame = useCurrentFrame();
  const opacity = fadeIn(frame, delay);
  const y = slideUp(frame, delay);
  return (
    <div style={{ opacity, transform: `translateY(${y}px)`, ...style }}>
      {children}
    </div>
  );
};

// --- Header / Navbar ---
const Header = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = scaleIn(frame, fps, 0);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "32px 48px",
        opacity: interpolate(scale, [0, 1], [0, 1]),
        transform: `scale(${interpolate(scale, [0, 1], [0.9, 1])})`,
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: COLORS.gradientTeal,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: COLORS.white,
            fontSize: 22,
            fontWeight: 800,
          }}
        >
          ON
        </div>
        <span style={{ fontSize: 32, fontWeight: 700, color: COLORS.dark }}>
          onsocial
        </span>
      </div>
      {/* Nav Items */}
      <div style={{ display: "flex", gap: 24 }}>
        {["Discovery", "Analytics", "API"].map((item, i) => (
          <FadeSlide key={item} delay={5 + i * 4}>
            <span
              style={{
                fontSize: 22,
                color: item === "Analytics" ? COLORS.primary : COLORS.textLight,
                fontWeight: item === "Analytics" ? 700 : 500,
                padding: "8px 16px",
                borderRadius: 20,
                background: item === "Analytics" ? "#E6F4F3" : "transparent",
              }}
            >
              {item}
            </span>
          </FadeSlide>
        ))}
      </div>
    </div>
  );
};

// --- Hero Title ---
const HeroTitle = () => (
  <div style={{ textAlign: "center", padding: "20px 48px 0" }}>
    <FadeSlide delay={8}>
      <h1
        style={{
          fontSize: 72,
          fontWeight: 800,
          color: COLORS.dark,
          lineHeight: 1.1,
          margin: 0,
          letterSpacing: -1,
        }}
      >
        Creator
        <br />
        <span style={{ color: COLORS.primary }}>Analytics</span>
      </h1>
    </FadeSlide>
    <FadeSlide delay={14}>
      <p
        style={{
          fontSize: 28,
          color: COLORS.textLight,
          marginTop: 16,
          lineHeight: 1.4,
        }}
      >
        Deep insights into influencer performance,
        <br />
        audience quality & engagement trends
      </p>
    </FadeSlide>
  </div>
);

// --- Tab Switcher ---
const TabSwitcher = () => {
  const tabs = ["Influencer Insights", "Audience Insights", "Posts Insights"];
  return (
    <FadeSlide delay={20} style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 24 }}>
      {tabs.map((tab, i) => (
        <div
          key={tab}
          style={{
            padding: "14px 28px",
            borderRadius: 30,
            fontSize: 22,
            fontWeight: 600,
            background: i === 0 ? COLORS.dark : "transparent",
            color: i === 0 ? COLORS.white : COLORS.dark,
            border: i === 0 ? "none" : `2px solid ${COLORS.primary}`,
          }}
        >
          {tab}
        </div>
      ))}
    </FadeSlide>
  );
};

// --- Profile Card ---
const ProfileCard = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = scaleIn(frame, fps, 28);
  return (
    <div
      style={{
        margin: "28px 48px 0",
        background: COLORS.white,
        borderRadius: 28,
        padding: "32px",
        boxShadow: COLORS.cardShadow,
        display: "flex",
        alignItems: "center",
        gap: 24,
        opacity: interpolate(s, [0, 1], [0, 1]),
        transform: `scale(${interpolate(s, [0, 1], [0.85, 1])})`,
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 100,
          height: 100,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #f0abfc, #818cf8)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 40,
          color: COLORS.white,
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        SS
      </div>
      <div>
        <div style={{ fontSize: 32, fontWeight: 700, color: COLORS.dark }}>
          Sydney Sweeney
        </div>
        <div style={{ fontSize: 22, color: COLORS.textLight, marginTop: 4 }}>
          @sydney_sweeney
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            marginTop: 10,
          }}
        >
          {["Instagram", "TikTok"].map((p) => (
            <span
              key={p}
              style={{
                background: "#E6F4F3",
                color: COLORS.primary,
                fontSize: 18,
                fontWeight: 600,
                padding: "4px 14px",
                borderRadius: 12,
              }}
            >
              {p}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

// --- Stat Card ---
const StatCard = ({ label, value, change, positive, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = scaleIn(frame, fps, delay);

  // Animated counter
  const numericValue = parseFloat(value.replace(/[^0-9.]/g, ""));
  const suffix = value.replace(/[0-9.]/g, "");
  const currentVal = interpolate(s, [0, 1], [0, numericValue]);
  const displayVal =
    numericValue >= 1000
      ? currentVal.toFixed(0) + suffix
      : currentVal.toFixed(numericValue < 10 ? 2 : 0) + suffix;

  return (
    <div
      style={{
        background: COLORS.white,
        borderRadius: 22,
        padding: "26px 24px",
        boxShadow: COLORS.cardShadow,
        flex: 1,
        opacity: interpolate(s, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`,
      }}
    >
      <div style={{ fontSize: 18, color: COLORS.textLight, fontWeight: 500 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 40,
          fontWeight: 800,
          color: COLORS.dark,
          marginTop: 6,
          letterSpacing: -0.5,
        }}
      >
        {displayVal}
      </div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 600,
          color: positive ? COLORS.green : COLORS.red,
          marginTop: 6,
        }}
      >
        {positive ? "▲" : "▼"} {change}
      </div>
    </div>
  );
};

// --- Stats Grid ---
const StatsGrid = () => (
  <div
    style={{
      display: "flex",
      gap: 16,
      padding: "0 48px",
      marginTop: 24,
      flexWrap: "wrap",
    }}
  >
    <div style={{ display: "flex", gap: 16, width: "100%" }}>
      <StatCard label="Followers" value="25M" change="+2.1%" positive delay={38} />
      <StatCard label="Eng. Rate" value="2.82%" change="+0.4%" positive delay={42} />
    </div>
    <div style={{ display: "flex", gap: 16, width: "100%" }}>
      <StatCard label="Paid Perf." value="99.02%" change="+1.2%" positive delay={46} />
      <StatCard label="Avg Likes" value="711K" change="-0.8%" positive={false} delay={50} />
    </div>
  </div>
);

// --- Mini Line Chart (SVG) ---
const MiniChart = ({ data, color, label, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = scaleIn(frame, fps, delay);

  const width = 280;
  const height = 100;
  const padding = 8;
  const chartW = width - padding * 2;
  const chartH = height - padding * 2;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((d, i) => {
      const x = padding + (i / (data.length - 1)) * chartW;
      const y = padding + chartH - ((d - min) / range) * chartH;
      return `${x},${y}`;
    })
    .join(" ");

  // Animate the polyline by revealing progressively
  const visiblePoints = Math.ceil(data.length * progress);
  const animatedPoints = data
    .slice(0, visiblePoints)
    .map((d, i) => {
      const x = padding + (i / (data.length - 1)) * chartW;
      const y = padding + chartH - ((d - min) / range) * chartH;
      return `${x},${y}`;
    })
    .join(" ");

  // Fill area
  const firstX = padding;
  const lastX = padding + ((visiblePoints - 1) / (data.length - 1)) * chartW;
  const areaPoints = `${firstX},${height - padding} ${animatedPoints} ${lastX},${height - padding}`;

  return (
    <div
      style={{
        background: COLORS.white,
        borderRadius: 18,
        padding: 18,
        boxShadow: COLORS.cardShadow,
        flex: 1,
        opacity: interpolate(progress, [0, 0.3], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      }}
    >
      <div style={{ fontSize: 18, color: COLORS.textLight, fontWeight: 500, marginBottom: 8 }}>
        {label}
      </div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {visiblePoints > 1 && (
          <>
            <polygon points={areaPoints} fill={color} opacity={0.12} />
            <polyline
              points={animatedPoints}
              fill="none"
              stroke={color}
              strokeWidth={3}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        )}
        {/* Animated dot at the end */}
        {visiblePoints > 0 && (
          <circle
            cx={padding + ((visiblePoints - 1) / (data.length - 1)) * chartW}
            cy={
              padding +
              chartH -
              ((data[visiblePoints - 1] - min) / range) * chartH
            }
            r={5}
            fill={color}
          />
        )}
      </svg>
    </div>
  );
};

// --- Charts Row ---
const ChartsRow = () => {
  const followersData = [18, 19, 20, 21, 21.5, 23, 24, 25];
  const followingData = [320, 325, 330, 328, 335, 340, 338, 345];
  const likesData = [600, 650, 700, 680, 720, 690, 710, 711];
  return (
    <div style={{ padding: "0 48px", marginTop: 24, display: "flex", flexDirection: "column", gap: 14 }}>
      <MiniChart data={followersData} color={COLORS.primary} label="Followers Trend" delay={56} />
      <div style={{ display: "flex", gap: 14 }}>
        <MiniChart data={followingData} color={COLORS.accent} label="Following" delay={62} />
        <MiniChart data={likesData} color={COLORS.red} label="Likes" delay={66} />
      </div>
    </div>
  );
};

// --- Feature Cards (carousel-like) ---
const featureItems = [
  { icon: "👥", title: "Notable Followers", desc: "Discover brand mentions & audience interests" },
  { icon: "🎯", title: "Audience Data", desc: "Credibility, reachability & demographics" },
  { icon: "📊", title: "PDF & JSON Reports", desc: "Download detailed analytics reports" },
  { icon: "🔍", title: "1K+ Followers", desc: "Access any account with 1,000+ followers" },
  { icon: "⚡", title: "REST API", desc: "Available via API and web interface" },
  { icon: "📈", title: "Performance", desc: "Reels, likes, comments breakdown" },
];

const FeatureCards = () => (
  <div style={{ padding: "0 48px", marginTop: 28 }}>
    <FadeSlide delay={72}>
      <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.dark, marginBottom: 18 }}>
        Influencer Insights
      </div>
    </FadeSlide>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
      {featureItems.map((item, i) => (
        <FadeSlide
          key={item.title}
          delay={76 + i * 5}
          style={{ flex: "1 1 calc(50% - 7px)", minWidth: "40%" }}
        >
          <div
            style={{
              background: COLORS.white,
              borderRadius: 18,
              padding: "22px 20px",
              boxShadow: COLORS.cardShadow,
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 8 }}>{item.icon}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.dark }}>
              {item.title}
            </div>
            <div style={{ fontSize: 18, color: COLORS.textLight, marginTop: 4 }}>
              {item.desc}
            </div>
          </div>
        </FadeSlide>
      ))}
    </div>
  </div>
);

// --- Sample Reports ---
const sampleProfiles = [
  { name: "Cian Abion", followers: "520K", er: "16.47%", country: "USA" },
  { name: "Julia Beautx", followers: "4.3M", er: "10.5%", country: "Germany" },
  { name: "Neymar Jr", followers: "1.3M", er: "0.22%", country: "Brazil" },
];

const SampleReports = () => (
  <div style={{ padding: "0 48px", marginTop: 28 }}>
    <FadeSlide delay={108}>
      <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.dark, marginBottom: 18 }}>
        Free Sample Reports
      </div>
    </FadeSlide>
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {sampleProfiles.map((profile, i) => (
        <FadeSlide key={profile.name} delay={112 + i * 6}>
          <div
            style={{
              background: COLORS.white,
              borderRadius: 20,
              padding: "22px 24px",
              boxShadow: COLORS.cardShadow,
              display: "flex",
              alignItems: "center",
              gap: 18,
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: `hsl(${170 + i * 40}, 60%, 65%)`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                fontWeight: 700,
                color: COLORS.white,
                flexShrink: 0,
              }}
            >
              {profile.name
                .split(" ")
                .map((w) => w[0])
                .join("")}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 24, fontWeight: 700, color: COLORS.dark }}>
                {profile.name}
              </div>
              <div style={{ display: "flex", gap: 16, marginTop: 6 }}>
                <span style={{ fontSize: 18, color: COLORS.textLight }}>
                  {profile.followers} followers
                </span>
                <span style={{ fontSize: 18, color: COLORS.primary, fontWeight: 600 }}>
                  ER {profile.er}
                </span>
              </div>
            </div>
            <div
              style={{
                background: "#E6F4F3",
                padding: "8px 16px",
                borderRadius: 12,
                fontSize: 16,
                fontWeight: 600,
                color: COLORS.primary,
              }}
            >
              {profile.country}
            </div>
          </div>
        </FadeSlide>
      ))}
    </div>
  </div>
);

// --- Data Ribbons (colored tags section) ---
const dataPoints = [
  "Engagement Rate", "Avg Likes", "Comments", "Shares", "Saves",
  "Paid Post Perf.", "Hidden Likes", "Brand Affinity", "Hashtags",
  "Views", "Mentions", "Language", "Historical Data", "Contacts",
];

const DataRibbons = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{ padding: "0 48px", marginTop: 28 }}>
      <FadeSlide delay={130}>
        <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.dark, marginBottom: 18 }}>
          See Beyond the Numbers
        </div>
      </FadeSlide>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {dataPoints.map((dp, i) => {
          const delay = 134 + i * 2;
          const opacity = fadeIn(frame, delay, 10);
          const hue = (170 + i * 15) % 360;
          return (
            <div
              key={dp}
              style={{
                opacity,
                transform: `scale(${interpolate(opacity, [0, 1], [0.7, 1])})`,
                background: `hsl(${hue}, 50%, 92%)`,
                color: `hsl(${hue}, 55%, 35%)`,
                padding: "10px 20px",
                borderRadius: 24,
                fontSize: 20,
                fontWeight: 600,
              }}
            >
              {dp}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// --- Use Cases ---
const useCases = [
  { icon: "🔗", title: "API Integration", desc: "Connect via REST API" },
  { icon: "🖥️", title: "Web Interface", desc: "Easy browser access" },
  { icon: "🏷️", title: "White-Label", desc: "Custom branded platform" },
  { icon: "⚡", title: "Enterprise Speed", desc: "Blazing fast processing" },
];

const UseCases = () => (
  <div style={{ padding: "0 48px", marginTop: 28 }}>
    <FadeSlide delay={168}>
      <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.dark, marginBottom: 18 }}>
        Built for Every Workflow
      </div>
    </FadeSlide>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
      {useCases.map((uc, i) => (
        <FadeSlide key={uc.title} delay={172 + i * 5} style={{ flex: "1 1 calc(50% - 7px)" }}>
          <div
            style={{
              background: COLORS.white,
              borderRadius: 18,
              padding: "22px 20px",
              boxShadow: COLORS.cardShadow,
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 40, marginBottom: 8 }}>{uc.icon}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.dark }}>
              {uc.title}
            </div>
            <div style={{ fontSize: 17, color: COLORS.textLight, marginTop: 4 }}>
              {uc.desc}
            </div>
          </div>
        </FadeSlide>
      ))}
    </div>
  </div>
);

// --- Benefits ---
const benefits = [
  { icon: "⏱️", text: "Save Hours on Research" },
  { icon: "✅", text: "Find Verified Audiences" },
  { icon: "📊", text: "Data-Driven Campaigns" },
  { icon: "🚀", text: "Scale Confidently" },
];

const Benefits = () => (
  <div style={{ padding: "0 48px", marginTop: 28 }}>
    <FadeSlide delay={192}>
      <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.dark, marginBottom: 18 }}>
        Smarter Decisions
      </div>
    </FadeSlide>
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {benefits.map((b, i) => (
        <FadeSlide key={b.text} delay={196 + i * 5}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              background: COLORS.white,
              borderRadius: 18,
              padding: "20px 24px",
              boxShadow: COLORS.cardShadow,
            }}
          >
            <div style={{ fontSize: 36 }}>{b.icon}</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: COLORS.dark }}>
              {b.text}
            </div>
          </div>
        </FadeSlide>
      ))}
    </div>
  </div>
);

// --- CTA Section ---
const CTASection = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = scaleIn(frame, fps, 218);

  // Pulsing glow
  const pulse = interpolate(Math.sin(frame * 0.12), [-1, 1], [0.6, 1]);

  return (
    <div
      style={{
        margin: "28px 48px 0",
        background: COLORS.gradientTeal,
        borderRadius: 28,
        padding: "48px 32px",
        textAlign: "center",
        opacity: interpolate(s, [0, 1], [0, 1]),
        transform: `scale(${interpolate(s, [0, 1], [0.85, 1])})`,
        boxShadow: `0 0 ${40 * pulse}px rgba(43,122,120,${0.3 * pulse})`,
      }}
    >
      <div style={{ fontSize: 40, fontWeight: 800, color: COLORS.white, lineHeight: 1.2 }}>
        Ready to unlock
        <br />
        creator insights?
      </div>
      <div
        style={{
          marginTop: 24,
          display: "inline-block",
          background: COLORS.white,
          color: COLORS.primary,
          fontSize: 26,
          fontWeight: 700,
          padding: "16px 48px",
          borderRadius: 30,
        }}
      >
        Book a Demo
      </div>
    </div>
  );
};

// --- Footer ---
const Footer = () => (
  <FadeSlide delay={230} style={{ padding: "28px 48px 48px", textAlign: "center" }}>
    <div style={{ fontSize: 18, color: COLORS.textLight }}>
      Terms of Service · Privacy Policy
    </div>
    <div style={{ fontSize: 16, color: COLORS.textLight, marginTop: 8, opacity: 0.6 }}>
      © 2026 ON Social. All rights reserved.
    </div>
  </FadeSlide>
);

// ============================================================
// MAIN COMPOSITION — scene-by-scene with Sequences
// ============================================================
export const OnSocialAnalytics = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Global background with subtle animated gradient
  const bgHue = interpolate(frame, [0, durationInFrames], [170, 180]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, hsl(${bgHue}, 30%, 97%) 0%, hsl(${bgHue}, 25%, 94%) 100%)`,
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        overflow: "hidden",
      }}
    >
      {/* SCENE 1: Header + Hero (frames 0–90) */}
      <Sequence from={0} durationInFrames={180} name="Header & Hero">
        <AbsoluteFill>
          <Header />
          <div style={{ marginTop: 10 }}>
            <HeroTitle />
            <TabSwitcher />
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 2: Profile + Stats (frames 25–180) */}
      <Sequence from={25} durationInFrames={200} name="Profile & Stats">
        <AbsoluteFill style={{ top: 420 }}>
          <ProfileCard />
          <StatsGrid />
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 3: Charts (frames 55–200) */}
      <Sequence from={55} durationInFrames={200} name="Charts">
        <AbsoluteFill style={{ top: 890 }}>
          <ChartsRow />
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 4: Feature Cards (frames 70–300) — scrolls up */}
      <Sequence from={150} durationInFrames={200} name="Features">
        <AbsoluteFill
          style={{
            top: interpolate(
              frame,
              [150, 200],
              [1920, 60],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        >
          <FeatureCards />
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 5: Sample Reports (frames 200–370) */}
      <Sequence from={240} durationInFrames={200} name="Sample Reports">
        <AbsoluteFill
          style={{
            top: interpolate(
              frame,
              [240, 280],
              [1920, 60],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        >
          <SampleReports />
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 6: Data Ribbons (frames 300–420) */}
      <Sequence from={320} durationInFrames={180} name="Data Ribbons">
        <AbsoluteFill
          style={{
            top: interpolate(
              frame,
              [320, 355],
              [1920, 80],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        >
          <DataRibbons />
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 7: Use Cases (frames 380–500) */}
      <Sequence from={390} durationInFrames={160} name="Use Cases">
        <AbsoluteFill
          style={{
            top: interpolate(
              frame,
              [390, 420],
              [1920, 80],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        >
          <UseCases />
        </AbsoluteFill>
      </Sequence>

      {/* SCENE 8: Benefits + CTA (frames 450–600) */}
      <Sequence from={460} durationInFrames={140} name="Benefits & CTA">
        <AbsoluteFill
          style={{
            top: interpolate(
              frame,
              [460, 490],
              [1920, 60],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        >
          <Benefits />
          <div style={{ marginTop: 560 }}>
            <CTASection />
            <Footer />
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* EXIT — fade out at the very end */}
      {frame > durationInFrames - 20 && (
        <AbsoluteFill
          style={{
            background: "black",
            opacity: interpolate(
              frame,
              [durationInFrames - 20, durationInFrames],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        />
      )}
    </AbsoluteFill>
  );
};

export default OnSocialAnalytics;
