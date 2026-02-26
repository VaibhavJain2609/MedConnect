import "../../app/globals.css";

/**
 * Standalone layout for test-design-system page
 * Bypasses authentication to allow direct viewing of design tokens
 */
export default function TestDesignSystemLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-dreams-lightBg">
        {children}
      </body>
    </html>
  );
}
