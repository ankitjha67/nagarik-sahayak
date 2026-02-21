export const IndianFlag = ({ size = 28 }) => (
  <svg width={size} height={size * 0.67} viewBox="0 0 90 60" className="rounded-sm shadow-sm">
    <rect width="90" height="20" fill="#FF9933" />
    <rect y="20" width="90" height="20" fill="#FFFFFF" />
    <rect y="40" width="90" height="20" fill="#138808" />
    <circle cx="45" cy="30" r="6.5" fill="none" stroke="#000080" strokeWidth="1" />
    <circle cx="45" cy="30" r="1" fill="#000080" />
    {[...Array(24)].map((_, i) => {
      const angle = (i * 15 * Math.PI) / 180;
      return (
        <line
          key={i}
          x1={45 + 2 * Math.cos(angle)}
          y1={30 + 2 * Math.sin(angle)}
          x2={45 + 6 * Math.cos(angle)}
          y2={30 + 6 * Math.sin(angle)}
          stroke="#000080"
          strokeWidth="0.5"
        />
      );
    })}
  </svg>
);
