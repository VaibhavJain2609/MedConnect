'use client';

import { useState, useEffect } from 'react';
import { Brand, getBrandAlternatives } from '@/lib/api/medicines-emr';
import { RefreshCw, ShoppingCart } from 'lucide-react';

interface AlternativeMedicinesProps {
  brandId: string;
  brandName: string;
  currentComposition: string;
  onSelect?: (alternative: Brand) => void;
  className?: string;
}

export default function AlternativeMedicines({
  brandId,
  brandName,
  currentComposition,
  onSelect,
  className = '',
}: AlternativeMedicinesProps) {
  const [alternatives, setAlternatives] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAlternatives();
  }, [brandId]);

  const loadAlternatives = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getBrandAlternatives(brandId);
      setAlternatives(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alternatives');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className={`animate-pulse ${className}`}>
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-3"></div>
        <div className="space-y-2">
          <div className="h-16 bg-gray-100 rounded"></div>
          <div className="h-16 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 bg-red-50 p-4 ${className}`}>
        <p className="text-sm text-red-800">Error loading alternatives: {error}</p>
        <button
          onClick={loadAlternatives}
          className="mt-2 text-sm text-red-600 hover:text-red-700 font-medium flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  if (alternatives.length === 0) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-gray-50 p-4 ${className}`}>
        <p className="text-sm text-gray-600">
          No alternative brands found with the same composition ({currentComposition}).
        </p>
      </div>
    );
  }

  return (
    <div className={className}>
      <div className="mb-3">
        <h4 className="font-semibold text-gray-900 mb-1">
          Alternative Brands ({alternatives.length})
        </h4>
        <p className="text-xs text-gray-600">
          Same composition: {currentComposition}
        </p>
      </div>

      <div className="space-y-2">
        {alternatives.map((alternative) => (
          <div
            key={alternative.brand_id}
            className={`rounded-lg border ${
              alternative.is_discontinued
                ? 'border-gray-300 bg-gray-50'
                : 'border-green-200 bg-green-50'
            } p-3 hover:shadow-md transition-shadow`}
          >
            <div className="flex items-start justify-between gap-3">
              {/* Brand Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h5 className="font-medium text-gray-900 truncate">
                    {alternative.brand_name}
                  </h5>
                  {alternative.is_discontinued && (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-gray-200 text-gray-700">
                      DISCONTINUED
                    </span>
                  )}
                </div>

                {alternative.manufacturer && (
                  <p className="text-sm text-gray-600 mb-1">
                    by {alternative.manufacturer.manufacturer_name}
                  </p>
                )}

                <div className="text-xs text-gray-500">
                  {alternative.compositions.map((comp, idx) => (
                    <span key={comp.composition_id}>
                      {comp.salt_name} ({comp.display_strength})
                      {idx < alternative.compositions.length - 1 && ' + '}
                    </span>
                  ))}
                </div>

                {alternative.drug_type && alternative.drug_type !== 'allopathy' && (
                  <div className="mt-1">
                    <span className="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded">
                      {alternative.drug_type}
                    </span>
                  </div>
                )}
              </div>

              {/* Action Button */}
              {onSelect && !alternative.is_discontinued && (
                <button
                  onClick={() => onSelect(alternative)}
                  className="flex-shrink-0 px-3 py-1.5 text-sm font-medium text-green-700 bg-green-100 rounded-md hover:bg-green-200 transition-colors flex items-center gap-1"
                >
                  <ShoppingCart className="w-4 h-4" />
                  Select
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Info footer */}
      <div className="mt-3 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
        <strong>Note:</strong> Alternative brands contain the exact same active ingredients
        (salts) in identical strengths. Consult your doctor before switching medications.
      </div>
    </div>
  );
}
