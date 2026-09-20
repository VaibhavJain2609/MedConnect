/**
 * Tests for src/lib/utils.ts — cn(), formatDate(), recordTypeLabel(), recordTypeColor()
 */

import { cn, formatDate, recordTypeColor, recordTypeLabel } from '../utils'

describe('cn', () => {
  it('joins multiple class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('merges conflicting Tailwind classes, keeping the last', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
    expect(cn('text-sm', 'text-lg')).toBe('text-lg')
  })

  it('drops falsy conditional classes', () => {
    expect(cn('base', false && 'hidden', undefined, null)).toBe('base')
  })

  it('supports conditional object syntax', () => {
    expect(cn('base', { 'text-red-500': true, 'text-blue-500': false })).toBe(
      'base text-red-500'
    )
  })

  it('returns an empty string for no classes', () => {
    expect(cn()).toBe('')
  })
})

describe('formatDate', () => {
  it('formats a date in en-IN day-month-year style', () => {
    // Midday keeps the assertion stable regardless of the test runner's TZ.
    expect(formatDate('2024-06-15T12:00:00')).toBe('15 Jun 2024')
  })

  it('returns a non-empty human-readable string', () => {
    expect(formatDate('2024-01-15T12:00:00')).toMatch(/^\d{1,2} \w{3} \d{4}$/)
  })
})

describe('recordTypeLabel', () => {
  it('maps known record types to human labels', () => {
    expect(recordTypeLabel('prescription')).toBe('Prescription')
    expect(recordTypeLabel('lab_report')).toBe('Lab Report')
    expect(recordTypeLabel('opd_note')).toBe('OPD Note')
  })

  it('falls back to the raw type for unknown values', () => {
    expect(recordTypeLabel('mystery_type')).toBe('mystery_type')
  })
})

describe('recordTypeColor', () => {
  it('returns the mapped color classes for known types', () => {
    expect(recordTypeColor('prescription')).toBe('bg-blue-100 text-blue-800')
  })

  it('falls back to gray for unknown types', () => {
    expect(recordTypeColor('mystery_type')).toBe('bg-gray-100 text-gray-800')
  })
})
