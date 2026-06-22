import React from 'react'
import { Routes, Route } from 'react-router-dom'
import SessionList from './components/SessionList.jsx'
import ChatView from './components/ChatView.jsx'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/" element={<SessionList />} />
        <Route path="/:sessionId" element={<ChatView />} />
      </Routes>
    </div>
  )
}
