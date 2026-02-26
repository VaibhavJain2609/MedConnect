"use client";

/**
 * Design System Test Page
 * Verifies Dreams EMR colors, typography, and spacing tokens
 * Access at: http://localhost:3000/test-design-system
 *
 * DELETE THIS FILE after verifying Phase 1 completion
 */

export default function TestDesignSystem() {
  return (
    <div className="min-h-screen bg-dreams-lightBg p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h1 className="text-3xl font-bold text-dreams-textPrimary mb-2">
            Dreams EMR Design System Test
          </h1>
          <p className="text-dreams-textSecondary">
            Verifying Phase 1: Design System Foundation
          </p>
        </div>

        {/* Dreams Colors */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h2 className="text-2xl font-bold text-dreams-textPrimary mb-4">
            Dreams Colors
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="h-20 bg-dreams-blue rounded-md mb-2"></div>
              <p className="text-sm font-medium">dreams-blue</p>
              <p className="text-xs text-dreams-textSecondary">#4169E1</p>
            </div>
            <div>
              <div className="h-20 bg-dreams-darkSidebar rounded-md mb-2"></div>
              <p className="text-sm font-medium">dreams-darkSidebar</p>
              <p className="text-xs text-dreams-textSecondary">#1A1D1F</p>
            </div>
            <div>
              <div className="h-20 bg-dreams-lightBg rounded-md mb-2 border border-dreams-border"></div>
              <p className="text-sm font-medium">dreams-lightBg</p>
              <p className="text-xs text-dreams-textSecondary">#F5F7FA</p>
            </div>
          </div>
        </div>

        {/* Status Colors */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h2 className="text-2xl font-bold text-dreams-textPrimary mb-4">
            Status Colors
          </h2>
          <div className="grid grid-cols-5 gap-4">
            <div>
              <div className="h-20 bg-status-inProgress rounded-md mb-2"></div>
              <p className="text-sm font-medium">In Progress</p>
              <p className="text-xs text-dreams-textSecondary">#8B5CF6</p>
            </div>
            <div>
              <div className="h-20 bg-status-completed rounded-md mb-2"></div>
              <p className="text-sm font-medium">Completed</p>
              <p className="text-xs text-dreams-textSecondary">#10B981</p>
            </div>
            <div>
              <div className="h-20 bg-status-pending rounded-md mb-2"></div>
              <p className="text-sm font-medium">Pending</p>
              <p className="text-xs text-dreams-textSecondary">#F59E0B</p>
            </div>
            <div>
              <div className="h-20 bg-status-overdue rounded-md mb-2"></div>
              <p className="text-sm font-medium">Overdue</p>
              <p className="text-xs text-dreams-textSecondary">#EF4444</p>
            </div>
            <div>
              <div className="h-20 bg-status-upcoming rounded-md mb-2"></div>
              <p className="text-sm font-medium">Upcoming</p>
              <p className="text-xs text-dreams-textSecondary">#3B82F6</p>
            </div>
          </div>
        </div>

        {/* Typography Scale */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h2 className="text-2xl font-bold text-dreams-textPrimary mb-4">
            Typography Scale
          </h2>
          <div className="space-y-3">
            <p className="text-xs text-dreams-textSecondary">text-xs: The quick brown fox jumps over the lazy dog</p>
            <p className="text-sm text-dreams-textSecondary">text-sm: The quick brown fox jumps over the lazy dog</p>
            <p className="text-base text-dreams-textPrimary">text-base: The quick brown fox jumps over the lazy dog</p>
            <p className="text-lg text-dreams-textPrimary">text-lg: The quick brown fox jumps over the lazy dog</p>
            <p className="text-xl text-dreams-textPrimary">text-xl: The quick brown fox jumps over the lazy dog</p>
            <p className="text-2xl text-dreams-textPrimary">text-2xl: The quick brown fox jumps over the lazy dog</p>
            <p className="text-3xl text-dreams-textPrimary">text-3xl: The quick brown fox</p>
          </div>
        </div>

        {/* Shadows */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h2 className="text-2xl font-bold text-dreams-textPrimary mb-4">
            Shadows
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-dreams-lightBg p-6 rounded-lg shadow-card">
              <p className="font-medium">shadow-card</p>
              <p className="text-sm text-dreams-textSecondary">Default card shadow</p>
            </div>
            <div className="bg-dreams-lightBg p-6 rounded-lg shadow-card-hover">
              <p className="font-medium">shadow-card-hover</p>
              <p className="text-sm text-dreams-textSecondary">Hover state shadow</p>
            </div>
          </div>
        </div>

        {/* Buttons Preview */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h2 className="text-2xl font-bold text-dreams-textPrimary mb-4">
            Button Styles
          </h2>
          <div className="flex gap-4">
            <button className="px-4 py-2 bg-dreams-blue text-white rounded-md hover:opacity-90 transition-opacity">
              Primary Button
            </button>
            <button className="px-4 py-2 bg-white text-dreams-blue border border-dreams-blue rounded-md hover:bg-dreams-blue hover:text-white transition-colors">
              Secondary Button
            </button>
            <button className="px-4 py-2 bg-status-completed text-white rounded-md hover:opacity-90 transition-opacity">
              Success Button
            </button>
            <button className="px-4 py-2 bg-status-overdue text-white rounded-md hover:opacity-90 transition-opacity">
              Danger Button
            </button>
          </div>
        </div>

        {/* Status Badges */}
        <div className="bg-white p-6 rounded-lg shadow-card">
          <h2 className="text-2xl font-bold text-dreams-textPrimary mb-4">
            Status Badges
          </h2>
          <div className="flex gap-3 flex-wrap">
            <span className="px-3 py-1 bg-status-inProgress/10 text-status-inProgress text-sm font-medium rounded-full">
              In Progress
            </span>
            <span className="px-3 py-1 bg-status-completed/10 text-status-completed text-sm font-medium rounded-full">
              Completed
            </span>
            <span className="px-3 py-1 bg-status-pending/10 text-status-pending text-sm font-medium rounded-full">
              Pending
            </span>
            <span className="px-3 py-1 bg-status-overdue/10 text-status-overdue text-sm font-medium rounded-full">
              Overdue
            </span>
            <span className="px-3 py-1 bg-status-upcoming/10 text-status-upcoming text-sm font-medium rounded-full">
              Upcoming
            </span>
          </div>
        </div>

        {/* Delete Notice */}
        <div className="bg-status-pending/10 border border-status-pending p-4 rounded-lg">
          <p className="text-sm text-dreams-textPrimary">
            <strong>⚠️ Note:</strong> Delete this test page after verifying Phase 1 completion.
            <br />
            <code className="text-xs bg-white px-2 py-1 rounded mt-2 inline-block">
              rm /Users/vaibhavjain/projects/MedConnect/frontend/src/app/test-design-system/page.tsx
            </code>
          </p>
        </div>
      </div>
    </div>
  );
}
