import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-dreams-lightBg">
      <div className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow-lg text-center">
        <div className="space-y-2">
          <h1 className="text-6xl font-bold text-dreams-blue">404</h1>
          <h2 className="text-2xl font-bold text-dreams-textPrimary">
            Page Not Found
          </h2>
          <p className="text-dreams-textSecondary">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>

        <Link
          href="/"
          className="inline-block rounded-lg bg-dreams-blue px-6 py-3 text-white hover:opacity-90 transition-opacity"
        >
          Go back home
        </Link>
      </div>
    </div>
  );
}
