export default function StatusPill({ tone = "green", children, dot = true, className = "" }) {
  return (
    <span className={`admin-status-pill admin-status-pill--${tone} ${className}`}>
      {dot && <i />}
      {children}
    </span>
  );
}
