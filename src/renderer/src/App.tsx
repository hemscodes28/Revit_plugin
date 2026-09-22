import React, { useState, useEffect } from 'react'
import {
  type Conversation,
  type Message,
  type SearchResult,
  loadConversations,
  saveConversations,
  loadActiveId,
  saveActiveId,
  createNewConversation,
  generateTitleFromQuery,
} from './utils/storage'
import { ChatSidebar } from './components/ChatSidebar'
import { ChatHeader } from './components/ChatHeader'
import { WelcomeScreen } from './components/WelcomeScreen'
import { ChatMessage } from './components/ChatMessage'
import { TypingIndicator } from './components/TypingIndicator'
import { ChatInput } from './components/ChatInput'

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isConnected, setIsConnected] = useState(true)
  const [activeProjectName, setActiveProjectName] = useState<string | null>(null)

  // Poll active project from backend/Revit plugin dynamically
  useEffect(() => {
    const fetchActiveProject = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/current-project')
        if (res.ok) {
          const data = await res.json()
          if (data.success && data.project_name) {
            setActiveProjectName(data.project_name)
            setIsConnected(Boolean(data.live))
          } else {
            setActiveProjectName(null)
            setIsConnected(false)
          }
        } else {
          setIsConnected(false)
        }
      } catch {
        setIsConnected(false)
      }
    }

    fetchActiveProject()
    const interval = setInterval(fetchActiveProject, 3000)
    return () => clearInterval(interval)
  }, [])

  // Initial load from localStorage
  useEffect(() => {
    const loaded = loadConversations()
    const storedActiveId = loadActiveId()

    if (loaded.length > 0) {
      setConversations(loaded)
      if (storedActiveId && loaded.some((c) => c.id === storedActiveId)) {
        setActiveId(storedActiveId)
      } else {
        setActiveId(loaded[0].id)
        saveActiveId(loaded[0].id)
      }
    } else {
      const newConv = createNewConversation()
      setConversations([newConv])
      setActiveId(newConv.id)
      saveConversations([newConv])
      saveActiveId(newConv.id)
    }
  }, [])

  // Auto-save conversations when state changes
  useEffect(() => {
    if (conversations.length > 0) {
      saveConversations(conversations)
    }
  }, [conversations])

  // Get active conversation object
  const activeConversation = conversations.find((c) => c.id === activeId) || null

  // Create new chat
  const handleNewChat = () => {
    const newConv = createNewConversation()
    setConversations((prev) => [newConv, ...prev])
    setActiveId(newConv.id)
    saveActiveId(newConv.id)
    setError('')
  }

  // Clear current conversation messages
  const handleClearChat = () => {
    if (!activeId) return
    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeId ? { ...c, messages: [], updatedAt: Date.now() } : c
      )
    )
    setError('')
  }

  // Select conversation
  const handleSelectConversation = (id: string) => {
    setActiveId(id)
    saveActiveId(id)
    setError('')
  }

  // Rename conversation
  const handleRenameConversation = (id: string, newTitle: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: newTitle } : c))
    )
  }

  // Delete conversation
  const handleDeleteConversation = (id: string) => {
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id)
      if (filtered.length === 0) {
        const fresh = createNewConversation()
        setActiveId(fresh.id)
        saveActiveId(fresh.id)
        return [fresh]
      }
      if (activeId === id) {
        setActiveId(filtered[0].id)
        saveActiveId(filtered[0].id)
      }
      return filtered
    })
  }

  // Execute Revit Action (OPEN, SELECT, HIGHLIGHT, ZOOM)
  const handleExecuteRevitAction = async (result: SearchResult, actionName: string = 'OPEN') => {
    try {
      setError('')
      const payload = {
        ...result,
        action: actionName.toUpperCase(),
      }

      console.log('Executing Revit action:', payload)
      let res: { success?: boolean; message?: string } | null = null

      if (window.electronAPI && window.electronAPI.openRevitResult) {
        res = await window.electronAPI.openRevitResult(payload as any)
      } else {
        const response = await fetch('http://127.0.0.1:8000/revit-action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        res = await response.json()
      }

      if (res && !res.success) {
        setIsConnected(false)
        setError(res.message || 'Revit action failed. Please check that Revit is running.')
      } else if (res && res.success) {
        setIsConnected(true)
      }
    } catch (err) {
      console.error('Revit action error:', err)
      setIsConnected(false)
      setError('Could not communicate with the Revit plugin. Please check that Revit is running.')
    }
  }

  // Send Message
  const handleSendMessage = async (textToSend?: string) => {
    const rawQuery = textToSend || inputMessage
    const trimmed = rawQuery.trim()
    if (!trimmed || loading || !activeId) return

    const userMessage: Message = {
      id: `msg_${Date.now()}_u`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    }

    // Append user message & auto-generate title if this is the first message
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id === activeId) {
          const isFirstMessage = c.messages.length === 0
          const title = isFirstMessage ? generateTitleFromQuery(trimmed) : c.title
          return {
            ...c,
            title,
            updatedAt: Date.now(),
            messages: [...c.messages, userMessage],
          }
        }
        return c
      })
    )

    setInputMessage('')
    setError('')
    setLoading(true)

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed }),
      })

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`)
      }

      const data = await response.json()
      setIsConnected(true)

      // Try updating active project name if returned in backend results or project info
      if (data.results && data.results.length > 0 && data.results[0].project_name) {
        setActiveProjectName(data.results[0].project_name)
      }

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_a`,
        role: 'assistant',
        content: data.message || data.response || 'No response text available.',
        timestamp: Date.now(),
        type: data.type,
        intent: data.intent,
        results: data.results || [],
      }

      setConversations((prev) =>
        prev.map((c) => {
          if (c.id === activeId) {
            return {
              ...c,
              updatedAt: Date.now(),
              messages: [...c.messages, assistantMessage],
            }
          }
          return c
        })
      )
    } catch (err) {
      console.error('Failed to communicate with backend:', err)
      setIsConnected(false)
      const errText = err instanceof Error ? err.message : 'Unknown error'
      setError(`Unable to connect to RevitAI backend. ${errText}`)

      const fallbackAssistantMessage: Message = {
        id: `msg_${Date.now()}_err`,
        role: 'assistant',
        content: 'I could not connect to the RevitAI backend. Please check that python server is running.',
        timestamp: Date.now(),
      }

      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeId
            ? { ...c, updatedAt: Date.now(), messages: [...c.messages, fallbackAssistantMessage] }
            : c
        )
      )
    } finally {
      setLoading(false)
    }
  }

  const currentMessages = activeConversation?.messages || []

  return (
    <div className="app-container">
      {/* Collapsible Left Sidebar */}
      <ChatSidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        conversations={conversations}
        activeId={activeId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Main Workspace */}
      <div className="main-wrapper">
        <ChatHeader
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          activeProjectName={activeProjectName}
          isConnected={isConnected}
          onNewChat={handleNewChat}
          onClearChat={handleClearChat}
        />

        {error && <div className="error-banner">{error}</div>}

        <main className="chat-container">
          {currentMessages.length === 0 ? (
            <WelcomeScreen onSelectSuggestion={(q) => handleSendMessage(q)} />
          ) : (
            currentMessages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} onAction={handleExecuteRevitAction} />
            ))
          )}

          {loading && <TypingIndicator />}
        </main>

        <ChatInput
          value={inputMessage}
          onChange={setInputMessage}
          onSend={() => handleSendMessage()}
          loading={loading}
        />
      </div>
    </div>
  )
}

export default App