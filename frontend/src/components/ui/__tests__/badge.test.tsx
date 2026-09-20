/**
 * Badge Component Tests
 * Replaces the tautological PrescriptionFormExample tests — exercises a real
 * component import with variant/class assertions.
 */

import { render, screen } from '../../../../tests/utils/test-utils'
import { Badge } from '../badge'

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge>In Progress</Badge>)
    expect(screen.getByText('In Progress')).toBeInTheDocument()
  })

  it('applies the default variant classes', () => {
    render(<Badge>Default</Badge>)
    const el = screen.getByText('Default')
    expect(el.className).toContain('bg-dreams-blue')
    expect(el.className).toContain('rounded-full')
  })

  it('applies the destructive variant', () => {
    render(<Badge variant="destructive">Error</Badge>)
    expect(screen.getByText('Error').className).toContain('bg-destructive')
  })

  it('applies Dreams EMR status variants', () => {
    render(<Badge variant="inProgress">Active</Badge>)
    const el = screen.getByText('Active')
    expect(el.className).toContain('text-status-inProgress')
  })

  it('merges a custom className over variant classes', () => {
    render(<Badge className="px-10">Custom</Badge>)
    const el = screen.getByText('Custom')
    // tailwind-merge keeps the later px-* utility
    expect(el.className).toContain('px-10')
    expect(el.className).not.toContain('px-2.5')
  })
})
