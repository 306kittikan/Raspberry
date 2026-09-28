import React from 'react'

// ไอคอน SVG แบบ inline ทั้งหมด (ไม่พึ่งไลบรารีภายนอก ลดภาระของ Raspberry Pi)
const base = (props) => ({
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  ...props,
})

export const IconDatabase = (p) => (
  <svg {...base(p)}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
    <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
  </svg>
)

export const IconSparkle = (p) => (
  <svg {...base(p)}>
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
    <path d="M18.5 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z" />
  </svg>
)

export const IconMic = (p) => (
  <svg {...base(p)}>
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v4" />
  </svg>
)

export const IconWifiOff = (p) => (
  <svg {...base(p)}>
    <path d="M2 2l20 20" />
    <path d="M8.5 16.5a5 5 0 0 1 7 0" />
    <path d="M5 12.9a10 10 0 0 1 4-2.5" />
    <path d="M19 12.9a10 10 0 0 0-6.5-2.8" />
    <path d="M2 8.8a15 15 0 0 1 5-3.2" />
    <path d="M22 8.8a15 15 0 0 0-10.4-3.7" />
    <path d="M12 20h.01" />
  </svg>
)

export const IconFace = (p) => (
  <svg {...base(p)}>
    <path d="M4 8V6a2 2 0 0 1 2-2h2" />
    <path d="M16 4h2a2 2 0 0 1 2 2v2" />
    <path d="M20 16v2a2 2 0 0 1-2 2h-2" />
    <path d="M8 20H6a2 2 0 0 1-2-2v-2" />
    <circle cx="9.5" cy="10.5" r="1" fill="currentColor" stroke="none" />
    <circle cx="14.5" cy="10.5" r="1" fill="currentColor" stroke="none" />
    <path d="M9 14.5a4 4 0 0 0 6 0" />
  </svg>
)

export const IconKeypad = (p) => (
  <svg {...base(p)}>
    <rect x="3" y="3" width="4" height="4" rx="1" />
    <rect x="10" y="3" width="4" height="4" rx="1" />
    <rect x="17" y="3" width="4" height="4" rx="1" />
    <rect x="3" y="10" width="4" height="4" rx="1" />
    <rect x="10" y="10" width="4" height="4" rx="1" />
    <rect x="17" y="10" width="4" height="4" rx="1" />
    <rect x="3" y="17" width="4" height="4" rx="1" />
    <rect x="10" y="17" width="4" height="4" rx="1" />
    <rect x="17" y="17" width="4" height="4" rx="1" />
  </svg>
)

export const IconIncognito = (p) => (
  <svg {...base(p)}>
    <path d="M3 12h18" />
    <path d="M6 12l1.5-5A2 2 0 0 1 9.4 5.5h5.2A2 2 0 0 1 16.5 7L18 12" />
    <circle cx="7.5" cy="16" r="3" />
    <circle cx="16.5" cy="16" r="3" />
    <path d="M10.5 16a2 2 0 0 1 3 0" />
  </svg>
)

export const IconClock = (p) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
)

export const IconPin = (p) => (
  <svg {...base(p)}>
    <path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z" />
    <circle cx="12" cy="10" r="2.5" />
  </svg>
)

export const IconCalendar = (p) => (
  <svg {...base(p)}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </svg>
)

export const IconLogout = (p) => (
  <svg {...base(p)}>
    <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" />
    <path d="M10 17l-5-5 5-5" />
    <path d="M5 12h10" />
  </svg>
)

export const IconShield = (p) => (
  <svg {...base(p)}>
    <path d="M12 3l7 3v6c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
)

export const IconTrash = (p) => (
  <svg {...base(p)}>
    <path d="M4 7h16" />
    <path d="M10 11v6M14 11v6" />
    <path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" />
    <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
  </svg>
)

export const IconCheck = (p) => (
  <svg {...base(p)}>
    <path d="M4 12.5l5.5 5.5L20 6.5" />
  </svg>
)

export const IconClose = (p) => (
  <svg {...base(p)}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
)

export const IconWarning = (p) => (
  <svg {...base(p)}>
    <path d="M12 4l9 16H3l9-16z" />
    <path d="M12 10v4M12 17.5h.01" />
  </svg>
)

export const IconCameraOff = (p) => (
  <svg {...base(p)}>
    <path d="M2 2l20 20" />
    <path d="M7 7H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h13" />
    <path d="M22 17V9a2 2 0 0 0-2-2h-4l-1.5-2h-5" />
  </svg>
)

export const IconUsers = (p) => (
  <svg {...base(p)}>
    <circle cx="8" cy="9" r="3" />
    <circle cx="17" cy="9" r="2.5" />
    <path d="M2.5 19a5.5 5.5 0 0 1 11 0" />
    <path d="M15 14.5a5 5 0 0 1 6.5 4.5" />
  </svg>
)

export const IconSettings = (p) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
  </svg>
)

/** เครื่องบินกระดาษ — ปุ่มส่งคำถามในหน้าต่างแชท */
export const IconSend = (p) => (
  <svg {...base(p)}>
    <path d="M21.5 2.5 11 13" />
    <path d="M21.5 2.5 15 21.5l-4-8.5-8.5-4z" />
  </svg>
)

export const IconArrowRight = (p) => (
  <svg {...base(p)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
)

export const IconArrowLeft = (p) => (
  <svg {...base(p)}>
    <path d="M19 12H5M11 18l-6-6 6-6" />
  </svg>
)

export const IconBell = (p) => (
  <svg {...base(p)}>
    <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z" />
    <path d="M10.5 19a1.8 1.8 0 0 0 3 0" />
  </svg>
)

export const IconLogo = (p) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" {...p}>
    <circle cx="32" cy="32" r="30" stroke="currentColor" strokeWidth="3" />
    <path
      d="M32 14c7 5 11 11 11 18 0 7-5 12-11 12s-11-5-11-12c0-7 4-13 11-18z"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinejoin="round"
    />
    <path d="M32 26v24" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    <path d="M24 36h16" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
)

export const IconSpeaker = (p) => (
  <svg {...base(p)}>
    <path d="M11 5L6 9H3v6h3l5 4V5z" />
    <path d="M15.5 8.5a5 5 0 0 1 0 7" />
    <path d="M18.5 5.5a9 9 0 0 1 0 13" />
  </svg>
)

export const IconSpeakerOff = (p) => (
  <svg {...base(p)}>
    <path d="M11 5L6 9H3v6h3l5 4V5z" />
    <path d="M22 9l-6 6" />
    <path d="M16 9l6 6" />
  </svg>
)
