import React from 'react';
import { Brain, Sparkles } from 'lucide-react';
import type { ICPEntry } from '../../api/learning';
import type { ThemeTokens } from '../../lib/themeColors';

interface Props {
  entries: ICPEntry[];
  isDark: boolean;
  t: ThemeTokens;
}

function formatKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderValue(value: any, t: ThemeTokens, isDark: boolean): React.ReactElement {
  if (Array.isArray(value)) {
    return (
      <div className="flex flex-wrap gap-1.5 mt-1.5">
        {value.map((item, i) => (
          <span
            key={i}
            className="inline-block px-2 py-0.5 rounded text-[12px]"
            style={{ background: isDark ? '#2d2d2d' : '#f0f0f0', color: t.text2 }}
          >
            {String(item)}
          </span>
        ))}
      </div>
    );
  }
  if (typeof value === 'object' && value !== null) {
    return (
      <div className="mt-1.5 space-y-2">
        {Object.entries(value).map(([k, v]) => (
          <div key={k}>
            <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color: t.text4 }}>
              {formatKey(k)}
            </span>
            {renderValue(v, t, isDark)}
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-[13px]" style={{ color: t.text2 }}>{String(value)}</span>;
}

export function ICPPanel({ entries, isDark, t }: Props) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16" style={{ color: t.text4 }}>
        <Brain className="w-10 h-10 mb-3 opacity-40" />
        <p className="text-[14px] font-medium">No ICP data yet</p>
        <p className="text-[12px] mt-1" style={{ color: t.text5 }}>
          Run a learning cycle or submit feedback to populate ICP insights
        </p>
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <Brain className="w-4 h-4" style={{ color: t.text3 }} />
        <span className="text-[14px] font-medium" style={{ color: t.text1 }}>
          Ideal Customer Profile
        </span>
        <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ color: t.text4, background: isDark ? '#2d2d2d' : '#f0f0f0' }}>
          {entries.length} entries
        </span>
      </div>

      <div className="grid gap-3">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="rounded-lg border p-4"
            style={{ background: t.cardBg, borderColor: t.cardBorder }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[13px] font-medium" style={{ color: t.text1 }}>
                {entry.title || formatKey(entry.key)}
              </span>
              {entry.source === 'learning' && (
                <span
                  className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                  style={{
                    background: isDark ? 'rgba(139, 92, 246, 0.15)' : 'rgba(139, 92, 246, 0.1)',
                    color: isDark ? '#a78bfa' : '#7c3aed',
                  }}
                >
                  <Sparkles className="w-2.5 h-2.5" />
                  AI-learned
                </span>
              )}
            </div>
            {renderValue(entry.value, t, isDark)}
            {entry.updated_at && (
              <div className="mt-2 text-[10px]" style={{ color: t.text5 }}>
                Updated {new Date(entry.updated_at).toLocaleDateString()}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
