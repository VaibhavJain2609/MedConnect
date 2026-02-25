'use client';

import { DrugInteraction } from '@/lib/api/medicines-emr';
import { AlertTriangle, AlertCircle, Info, Ban } from 'lucide-react';

interface DrugInteractionWarningProps {
  interactions: DrugInteraction[];
  className?: string;
}

const severityConfig = {
  contraindicated: {
    icon: Ban,
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    textColor: 'text-red-900',
    iconColor: 'text-red-600',
    badgeColor: 'bg-red-100 text-red-800',
    label: 'CONTRAINDICATED',
  },
  major: {
    icon: AlertTriangle,
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    textColor: 'text-orange-900',
    iconColor: 'text-orange-600',
    badgeColor: 'bg-orange-100 text-orange-800',
    label: 'MAJOR',
  },
  moderate: {
    icon: AlertCircle,
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    textColor: 'text-yellow-900',
    iconColor: 'text-yellow-600',
    badgeColor: 'bg-yellow-100 text-yellow-800',
    label: 'MODERATE',
  },
  minor: {
    icon: Info,
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-900',
    iconColor: 'text-blue-600',
    badgeColor: 'bg-blue-100 text-blue-800',
    label: 'MINOR',
  },
};

export default function DrugInteractionWarning({
  interactions,
  className = '',
}: DrugInteractionWarningProps) {
  if (interactions.length === 0) {
    return null;
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-5 h-5 text-red-600" />
        <h3 className="font-semibold text-gray-900">
          Drug Interactions Detected ({interactions.length})
        </h3>
      </div>

      {interactions.map((interaction) => {
        const config = severityConfig[interaction.severity];
        const Icon = config.icon;

        return (
          <div
            key={interaction.interaction_id}
            className={`rounded-lg border-2 ${config.borderColor} ${config.bgColor} p-4`}
          >
            {/* Header */}
            <div className="flex items-start gap-3 mb-3">
              <Icon className={`w-5 h-5 ${config.iconColor} flex-shrink-0 mt-0.5`} />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`font-semibold ${config.textColor}`}>
                    {interaction.salt_1.name} + {interaction.salt_2.name}
                  </span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${config.badgeColor}`}>
                    {config.label}
                  </span>
                </div>
                {interaction.evidence_level && (
                  <div className="text-xs text-gray-600 mb-2">
                    Evidence: {interaction.evidence_level.replace('-', ' ')}
                  </div>
                )}
              </div>
            </div>

            {/* Effect */}
            <div className="mb-2">
              <p className={`text-sm ${config.textColor} leading-relaxed`}>
                {interaction.effect}
              </p>
            </div>

            {/* Mechanism */}
            {interaction.mechanism && (
              <div className="mb-2 pl-8">
                <div className="text-xs font-semibold text-gray-600 mb-1">Mechanism:</div>
                <p className="text-xs text-gray-700 italic">{interaction.mechanism}</p>
              </div>
            )}

            {/* Management */}
            {interaction.management && (
              <div className="pl-8">
                <div className="text-xs font-semibold text-gray-600 mb-1">Management:</div>
                <p className="text-xs text-gray-700 font-medium">{interaction.management}</p>
              </div>
            )}
          </div>
        );
      })}

      {/* Summary count by severity */}
      <div className="flex flex-wrap gap-2 text-xs pt-2 border-t border-gray-200">
        {Object.entries(
          interactions.reduce((acc, int) => {
            acc[int.severity] = (acc[int.severity] || 0) + 1;
            return acc;
          }, {} as Record<string, number>)
        ).map(([severity, count]) => {
          const config = severityConfig[severity as keyof typeof severityConfig];
          return (
            <span key={severity} className={`px-2 py-1 rounded ${config.badgeColor}`}>
              {count} {config.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
