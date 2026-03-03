/**
 * Word-level diff component using LCS algorithm.
 * Shows removed words (red + strikethrough) and added words (green highlight).
 */

type Segment = { type: 'equal' | 'removed' | 'added'; text: string };

function lcs(a: string[], b: string[]): number[][] {
  const m = a.length, n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  return dp;
}

function computeDiff(oldText: string, newText: string): Segment[] {
  const oldWords = oldText.split(/(\s+)/);
  const newWords = newText.split(/(\s+)/);
  const dp = lcs(oldWords, newWords);
  const segments: Segment[] = [];

  let i = oldWords.length, j = newWords.length;
  const raw: Segment[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
      raw.push({ type: 'equal', text: oldWords[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      raw.push({ type: 'added', text: newWords[j - 1] });
      j--;
    } else {
      raw.push({ type: 'removed', text: oldWords[i - 1] });
      i--;
    }
  }
  raw.reverse();

  // Merge consecutive segments of the same type
  for (const seg of raw) {
    const last = segments[segments.length - 1];
    if (last && last.type === seg.type) {
      last.text += seg.text;
    } else {
      segments.push({ ...seg });
    }
  }
  return segments;
}

export function TextDiff({
  oldText,
  newText,
  isDark,
}: {
  oldText: string;
  newText: string;
  isDark: boolean;
}) {
  const segments = computeDiff(oldText, newText);

  return (
    <div className="text-[12px] whitespace-pre-wrap leading-relaxed">
      {segments.map((seg, i) => {
        if (seg.type === 'removed') {
          return (
            <span
              key={i}
              className="line-through"
              style={{
                background: isDark ? 'rgba(127,29,29,0.3)' : '#fee2e2',
                color: isDark ? '#fca5a5' : '#991b1b',
              }}
            >
              {seg.text}
            </span>
          );
        }
        if (seg.type === 'added') {
          return (
            <span
              key={i}
              style={{
                background: isDark ? 'rgba(5,46,22,0.4)' : '#dcfce7',
                color: isDark ? '#4ade80' : '#166534',
              }}
            >
              {seg.text}
            </span>
          );
        }
        return <span key={i}>{seg.text}</span>;
      })}
    </div>
  );
}
