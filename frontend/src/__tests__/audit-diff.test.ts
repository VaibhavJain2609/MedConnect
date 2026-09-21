/**
 * Unit tests for diffValues() — the pure field-level diff helper behind
 * the audit-log expanded-row diff viewer.
 */

import { diffValues } from '@/components/admin/audit-diff'

describe('diffValues', () => {
  it('returns an empty array when both sides are null/empty', () => {
    expect(diffValues(null, null)).toEqual([])
    expect(diffValues(undefined, {})).toEqual([])
    expect(diffValues({}, {})).toEqual([])
  })

  it('marks keys present only in new_values as added', () => {
    const rows = diffValues(null, { name: 'Ada', active: true })
    expect(rows).toEqual([
      expect.objectContaining({
        key: 'name',
        status: 'added',
        hasOld: false,
        hasNew: true,
        newValue: 'Ada',
      }),
      expect.objectContaining({
        key: 'active',
        status: 'added',
        hasOld: false,
        hasNew: true,
        newValue: true,
      }),
    ])
  })

  it('marks keys present only in old_values as removed', () => {
    const rows = diffValues({ name: 'Ada', deleted_at: null }, undefined)
    expect(rows.map((r) => [r.key, r.status])).toEqual([
      ['name', 'removed'],
      ['deleted_at', 'removed'],
    ])
    expect(rows[0]).toMatchObject({ hasOld: true, hasNew: false, oldValue: 'Ada' })
  })

  it('marks differing values as changed', () => {
    const rows = diffValues({ status: 'pending' }, { status: 'approved' })
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      key: 'status',
      status: 'changed',
      oldValue: 'pending',
      newValue: 'approved',
    })
  })

  it('marks identical values as unchanged, including null vs missing', () => {
    const rows = diffValues(
      { id: 'abc', note: null },
      { id: 'abc', note: null }
    )
    expect(rows.map((r) => r.status)).toEqual(['unchanged', 'unchanged'])
  })

  it('treats a type change (1 vs "1") as changed', () => {
    const [row] = diffValues({ count: 1 }, { count: '1' })
    expect(row.status).toBe('changed')
  })

  it('flattens nested objects one level with dotted keys', () => {
    const rows = diffValues(
      { patient: { name: 'Ada', age: 30 } },
      { patient: { name: 'Ada', age: 31 } }
    )
    expect(rows.map((r) => [r.key, r.status])).toEqual([
      ['patient.name', 'unchanged'],
      ['patient.age', 'changed'],
    ])
    expect(rows[1]).toMatchObject({ oldValue: 30, newValue: 31 })
  })

  it('handles a nested key appearing only on one side', () => {
    const rows = diffValues(
      { meta: { a: 1 } },
      { meta: { a: 1, b: 2 } }
    )
    expect(rows.map((r) => [r.key, r.status])).toEqual([
      ['meta.a', 'unchanged'],
      ['meta.b', 'added'],
    ])
  })

  it('keeps empty nested objects as their own key', () => {
    const rows = diffValues({ extra: {} }, { extra: {} })
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ key: 'extra', status: 'unchanged' })
  })

  it('compares leaf arrays/objects by value, not reference', () => {
    const rows = diffValues(
      { tags: ['a', 'b'] },
      { tags: ['a', 'b'] }
    )
    expect(rows[0].status).toBe('unchanged')
    const changed = diffValues({ tags: ['a'] }, { tags: ['a', 'b'] })
    expect(changed[0].status).toBe('changed')
  })

  it('orders rows old-keys-first, then new-only keys', () => {
    const rows = diffValues(
      { b: 1, a: 2 },
      { a: 3, c: 4 }
    )
    expect(rows.map((r) => r.key)).toEqual(['b', 'a', 'c'])
    expect(rows.map((r) => r.status)).toEqual(['removed', 'changed', 'added'])
  })
})
