export default function SkeletonLoader({ rows = 3 }) {
  return (
    <div className="admin-skeleton-stack">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="admin-skeleton" />
      ))}
    </div>
  );
}
