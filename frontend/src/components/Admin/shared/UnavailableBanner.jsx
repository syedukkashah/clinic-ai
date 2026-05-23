export default function UnavailableBanner({ endpoint, message = "Not yet implemented - Coming soon" }) {
  return (
    <div className="admin-unavailable">
      <span>{message}</span>
      {endpoint && <code>{endpoint}</code>}
    </div>
  );
}
