/**
 * Avatar Component Tests
 * Verifies testing infrastructure setup
 */

import { render, screen } from '../../../../tests/utils/test-utils'
import { Avatar } from '../avatar'

describe('Avatar', () => {
  it('renders successfully', () => {
    render(<Avatar fallback="JD" />)
    expect(screen.getByText('JD')).toBeInTheDocument()
  })

  it('displays fallback text when no image provided', () => {
    render(<Avatar fallback="Test User" />)
    expect(screen.getByText('Test User')).toBeInTheDocument()
  })

  it('applies correct size class for lg size', () => {
    const { container } = render(<Avatar fallback="JD" size="lg" />)
    const avatar = container.querySelector('[class*="h-16"]')
    expect(avatar).toBeInTheDocument()
  })

  it('shows status indicator when showStatus is true', () => {
    const { container } = render(
      <Avatar fallback="JD" showStatus statusColor="online" />
    )
    // Status dot should exist with absolute positioning
    const statusDot = container.querySelector('[class*="absolute"]')
    expect(statusDot).toBeTruthy()
  })
})
