/* Flat, decorative illustrations in the pastel LMS style. Purely decorative: aria-hidden. */

/** Student at a desk with a laptop, books and a floating chart card — for the green welcome banner. */
export function StudyIllustration({ className = "illus" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 240 140" aria-hidden>
      <ellipse cx="120" cy="132" rx="100" ry="7" fill="rgba(0,0,0,.10)" />
      {/* floating chart card */}
      <g transform="translate(150 6)">
        <rect width="78" height="52" rx="10" fill="#fff" />
        <rect x="10" y="30" width="8" height="14" rx="2" fill="#2fc483" />
        <rect x="23" y="20" width="8" height="24" rx="2" fill="#22a06b" />
        <rect x="36" y="26" width="8" height="18" rx="2" fill="#8a75ff" />
        <rect x="49" y="12" width="8" height="32" rx="2" fill="#22a06b" />
        <rect x="10" y="9" width="30" height="5" rx="2.5" fill="#e3f6ec" />
      </g>
      {/* desk */}
      <rect x="40" y="96" width="160" height="8" rx="4" fill="#fff" opacity=".95" />
      <rect x="54" y="104" width="6" height="26" rx="3" fill="#fff" opacity=".7" />
      <rect x="180" y="104" width="6" height="26" rx="3" fill="#fff" opacity=".7" />
      {/* books */}
      <rect x="150" y="78" width="40" height="7" rx="2" fill="#ffc457" />
      <rect x="154" y="71" width="34" height="7" rx="2" fill="#8a75ff" />
      <rect x="148" y="85" width="44" height="11" rx="2" fill="#ff8a80" />
      {/* laptop */}
      <rect x="86" y="70" width="46" height="26" rx="3" fill="#1d2433" />
      <rect x="90" y="74" width="38" height="18" rx="2" fill="#2fc483" opacity=".9" />
      <rect x="78" y="94" width="62" height="4" rx="2" fill="#e9edf1" />
      {/* person */}
      <circle cx="70" cy="42" r="11" fill="#f5c9a6" />
      <path d="M58 40c0-10 8-15 15-14 6 1 10 6 9 12-4-4-10-5-15-3-3 1-6 3-9 5z" fill="#1d2433" />
      <path d="M52 96c0-22 6-38 18-38s20 14 22 30l-8 2c-2-10-6-16-10-16" fill="#ffffff" />
      <path d="M78 74l18 10" stroke="#f5c9a6" strokeWidth="6" strokeLinecap="round" />
      <rect x="54" y="92" width="34" height="6" rx="3" fill="#6e56f0" />
      <circle cx="35" cy="30" r="5" fill="#fff" opacity=".35" />
      <circle cx="210" cy="78" r="4" fill="#fff" opacity=".4" />
    </svg>
  );
}

/** Small "report" illustration for the sidebar help card. */
export function ReportIllustration({ className = "illus" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 200 86" aria-hidden>
      <circle cx="100" cy="46" r="38" fill="#ffffff" opacity=".7" />
      <rect x="70" y="14" width="56" height="66" rx="8" fill="#fff" stroke="#e2e7ec" />
      <rect x="80" y="26" width="26" height="5" rx="2.5" fill="#22a06b" />
      <rect x="80" y="37" width="36" height="4" rx="2" fill="#e2e7ec" />
      <rect x="80" y="46" width="30" height="4" rx="2" fill="#e2e7ec" />
      <rect x="80" y="58" width="6" height="12" rx="1.5" fill="#2fc483" />
      <rect x="90" y="54" width="6" height="16" rx="1.5" fill="#8a75ff" />
      <rect x="100" y="61" width="6" height="9" rx="1.5" fill="#ffc457" />
      <circle cx="128" cy="68" r="13" fill="#22a06b" />
      <path d="M122 68l4 4 8-8" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="56" cy="30" r="5" fill="#ffc457" />
      <circle cx="150" cy="24" r="4" fill="#8a75ff" />
    </svg>
  );
}
