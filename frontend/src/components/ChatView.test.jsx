import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ChatView from './ChatView.jsx'

vi.mock('../hooks/useChat.js', () => ({
  useChat: vi.fn(),
}))

import { useChat } from '../hooks/useChat.js'

const mockDatasets = [
  { dataset_id: 'd1', original_filename: 'data.csv', table_name: 'data', row_count: 100 },
]

const mockMessages = [
  { id: 'm1', role: 'user', content: 'How many rows?' },
  { id: 'm2', role: 'assistant', content: 'There are 100 rows.', sql: 'SELECT COUNT(*) FROM data', results: [{ count: 100 }] },
]

describe('ChatView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderChat = (state = {}) => {
    useChat.mockReturnValue({
      session: { session_id: 's1', title: 'Test Session' },
      messages: [],
      datasets: [],
      loading: false,
      queryLoading: false,
      error: null,
      tokenUsage: null,
      sendQuery: vi.fn(),
      uploadFile: vi.fn(),
      refresh: vi.fn(),
      ...state,
    })
    return render(
      <MemoryRouter initialEntries={['/s1']}>
        <Routes>
          <Route path="/:sessionId" element={<ChatView />} />
        </Routes>
      </MemoryRouter>
    )
  }

  it('renders dataset list', () => {
    renderChat({ datasets: mockDatasets })
    expect(screen.getByText('data.csv')).toBeTruthy()
  })

  it('renders user and assistant messages', () => {
    renderChat({ messages: mockMessages })
    expect(screen.getByText('How many rows?')).toBeTruthy()
    expect(screen.getByText('There are 100 rows.')).toBeTruthy()
  })

  it('renders SQL disclosure for assistant messages', () => {
    renderChat({ messages: mockMessages })
    expect(screen.getByText('Show SQL')).toBeTruthy()
  })

  it('disables input while queryLoading', () => {
    renderChat({ queryLoading: true })
    const input = screen.getByRole('textbox')
    expect(input.disabled).toBe(true)
  })
})
