import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SessionList from './SessionList.jsx'

// Mock the hook
vi.mock('../hooks/useSessions.js', () => ({
  useSessions: vi.fn(),
}))

import { useSessions } from '../hooks/useSessions.js'

const mockSessions = [
  { session_id: 's1', title: 'Session One', created_at: '2026-01-01T00:00:00Z', message_count: 3, dataset_count: 1, updated_at: '2026-01-01T00:00:00Z' },
  { session_id: 's2', title: 'Session Two', created_at: '2026-01-02T00:00:00Z', message_count: 0, dataset_count: 0, updated_at: '2026-01-02T00:00:00Z' },
]

describe('SessionList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders sessions from mock data', () => {
    useSessions.mockReturnValue({
      sessions: mockSessions,
      loading: false,
      error: null,
      createSession: vi.fn(),
    })
    render(<MemoryRouter><SessionList /></MemoryRouter>)
    expect(screen.getByText('Session One')).toBeTruthy()
    expect(screen.getByText('Session Two')).toBeTruthy()
  })

  it('renders empty state when no sessions', () => {
    useSessions.mockReturnValue({
      sessions: [],
      loading: false,
      error: null,
      createSession: vi.fn(),
    })
    render(<MemoryRouter><SessionList /></MemoryRouter>)
    expect(screen.getByText(/No sessions yet/i)).toBeTruthy()
  })

  it('calls createSession on New Session button click', async () => {
    const createSession = vi.fn().mockResolvedValue({ session_id: 'new-id' })
    useSessions.mockReturnValue({
      sessions: [],
      loading: false,
      error: null,
      createSession,
    })
    render(<MemoryRouter><SessionList /></MemoryRouter>)
    fireEvent.click(screen.getByText(/\+ New Session/i))
    await waitFor(() => expect(createSession).toHaveBeenCalled())
  })
})
