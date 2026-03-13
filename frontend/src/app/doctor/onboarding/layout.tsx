export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-dreams-lightBg flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Logo / Brand */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-dreams-textPrimary">MedConnect</h1>
          <p className="mt-1 text-sm text-dreams-textSecondary">Doctor Onboarding</p>
        </div>
        {children}
      </div>
    </div>
  );
}
