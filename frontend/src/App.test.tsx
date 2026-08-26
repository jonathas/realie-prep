// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App routing', () => {
  it('renders a helpful page for unknown routes', () => {
    render(<MemoryRouter initialEntries={['/missing-page']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Back to Study/ }).getAttribute('href')).toBe('/')
  })
})
