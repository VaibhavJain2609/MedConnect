'use client';

import { useState, useEffect, useCallback } from 'react';
import { DrugInteraction, checkDrugInteractions } from '@/lib/api/medicines-emr';

interface UseDrugInteractionsOptions {
  /**
   * Automatically check interactions when salt IDs change
   * Default: true
   */
  autoCheck?: boolean;

  /**
   * Debounce delay in milliseconds
   * Default: 300ms
   */
  debounceMs?: number;
}

export function useDrugInteractions(
  saltIds: string[],
  options: UseDrugInteractionsOptions = {}
) {
  const { autoCheck = true, debounceMs = 300 } = options;

  const [interactions, setInteractions] = useState<DrugInteraction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkInteractions = useCallback(
    async (ids: string[]) => {
      // Need at least 2 medicines to check interactions
      if (ids.length < 2) {
        setInteractions([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const results = await checkDrugInteractions(ids);
        setInteractions(results);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to check interactions');
        setInteractions([]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Auto-check with debounce
  useEffect(() => {
    if (!autoCheck) return;

    const timer = setTimeout(() => {
      checkInteractions(saltIds);
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [saltIds, autoCheck, debounceMs, checkInteractions]);

  // Manual check function
  const manualCheck = useCallback(() => {
    return checkInteractions(saltIds);
  }, [saltIds, checkInteractions]);

  // Helper functions
  const hasContraindicated = interactions.some((i) => i.severity === 'contraindicated');
  const hasMajor = interactions.some((i) => i.severity === 'major');
  const hasModerate = interactions.some((i) => i.severity === 'moderate');
  const hasAny = interactions.length > 0;

  const countBySeverity = interactions.reduce((acc, interaction) => {
    acc[interaction.severity] = (acc[interaction.severity] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return {
    interactions,
    loading,
    error,
    hasContraindicated,
    hasMajor,
    hasModerate,
    hasAny,
    countBySeverity,
    checkInteractions: manualCheck,
    refresh: manualCheck,
  };
}
