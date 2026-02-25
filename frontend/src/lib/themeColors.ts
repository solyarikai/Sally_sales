/** Shared dark/light theme color tokens used across all pages. */
export function themeColors(isDark: boolean) {
  return isDark
    ? {
        pageBg: '#1e1e1e',
        headerBg: '#252526',
        cardBg: '#252526',
        cardBorder: '#333',
        cardHoverBorder: '#3c3c3c',
        divider: '#2d2d2d',
        inputBg: '#3c3c3c',
        inputBorder: 'transparent',
        inputFocusBorder: '#505050',
        draftBg: '#1e1e1e',
        draftBorder: '#3c3c3c',
        text1: '#d4d4d4',   // primary
        text2: '#b0b0b0',   // secondary
        text3: '#969696',   // tertiary
        text4: '#858585',   // muted
        text5: '#6e6e6e',   // dim
        text6: '#4e4e4e',   // subtle
        badgeBg: '#2d2d2d',
        badgeText: '#858585',
        btnPrimaryBg: '#d4d4d4',
        btnPrimaryHover: '#e0e0e0',
        btnPrimaryText: '#1e1e1e',
        btnGhostHover: '#2d2d2d',
        threadInbound: '#2d2d2d',
        threadOutbound: '#37373d',
        reasoningBg: '#1e1e1e',
        reasoningBorder: '#2d2d2d',
        toastBg: '#252526',
        toastText: '#d4d4d4',
        toastBorder: '#3c3c3c',
        toastErrText: '#d4a4a4',
        errorBg: '#3a2020',
        errorBorder: '#5a3030',
        errorText: '#d4a4a4',
        warnText: '#d4a464',
        scrollThumb: 'rgba(255,255,255,0.1)',
      }
    : {
        pageBg: '#f5f5f5',
        headerBg: '#ffffff',
        cardBg: '#ffffff',
        cardBorder: '#e0e0e0',
        cardHoverBorder: '#ccc',
        divider: '#eee',
        inputBg: '#f0f0f0',
        inputBorder: '#ddd',
        inputFocusBorder: '#bbb',
        draftBg: '#f8f8f8',
        draftBorder: '#ddd',
        text1: '#1a1a1a',
        text2: '#333',
        text3: '#555',
        text4: '#777',
        text5: '#999',
        text6: '#bbb',
        badgeBg: '#eee',
        badgeText: '#666',
        btnPrimaryBg: '#333',
        btnPrimaryHover: '#222',
        btnPrimaryText: '#fff',
        btnGhostHover: '#eee',
        threadInbound: '#f0f4ff',
        threadOutbound: '#f0f0f0',
        reasoningBg: '#f8f8f8',
        reasoningBorder: '#e8e8e8',
        toastBg: '#fff',
        toastText: '#333',
        toastBorder: '#ddd',
        toastErrText: '#c44',
        errorBg: '#fef2f2',
        errorBorder: '#fecaca',
        errorText: '#b91c1c',
        warnText: '#b45309',
        scrollThumb: 'rgba(0,0,0,0.12)',
      };
}

export type ThemeTokens = ReturnType<typeof themeColors>;
