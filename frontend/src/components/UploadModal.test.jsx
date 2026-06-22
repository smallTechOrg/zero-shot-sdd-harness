import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import UploadModal from './UploadModal.jsx'

describe('UploadModal', () => {
  it('renders drag-drop zone', () => {
    render(<UploadModal onUpload={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/Drop a file here/i)).toBeTruthy()
  })

  it('shows success state with table_name and row_count', async () => {
    const onUpload = vi.fn().mockResolvedValue({
      original_filename: 'test.csv',
      table_name: 'test',
      row_count: 42,
    })
    render(<UploadModal onUpload={onUpload} onClose={vi.fn()} />)
    const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]')
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/test.csv uploaded/i)).toBeTruthy())
    // table_name is rendered inside a <code> element
    expect(screen.getByText('test')).toBeTruthy()
    expect(screen.getByText(/42/)).toBeTruthy()
  })

  it('shows error state on upload failure', async () => {
    const onUpload = vi.fn().mockRejectedValue({ message: 'File too large' })
    render(<UploadModal onUpload={onUpload} onClose={vi.fn()} />)
    const file = new File(['data'], 'big.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]')
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/File too large/i)).toBeTruthy())
  })
})
