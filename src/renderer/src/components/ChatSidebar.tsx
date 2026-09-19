import React, { useState } from 'react'
import {
  Plus,
  Search,
  MessageSquare,
  MoreVertical,
  Edit2,
  Trash2,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import type { Conversation } from '../utils/storage'
import { Tooltip } from './Tooltip'
import revitLogo from '../assets/revit-logo.png'

interface ChatSidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
  conversations: Conversation[]
  activeId: string | null
  onSelectConversation: (id: string) => void
  onNewChat: () => void
  onRenameConversation: (id: string, newTitle: string) => void
  onDeleteConversation: (id: string) => void
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  collapsed,
  onToggleCollapse,
  conversations,
  activeId,
  onSelectConversation,
  onNewChat,
  onRenameConversation,
  onDeleteConversation,
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  // Filter conversations by search query
  const filteredConversations = conversations.filter((c) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      c.title.toLowerCase().includes(q) ||
      c.messages.some((m) => m.content.toLowerCase().includes(q))
    )
  })

  // Group conversations by time
  const groupConversations = (items: Conversation[]) => {
    const now = Date.now()
    const oneDay = 24 * 60 * 60 * 1000
    const today: Conversation[] = []
    const yesterday: Conversation[] = []
    const last7Days: Conversation[] = []
    const older: Conversation[] = []

    items.forEach((item) => {
      const diff = now - item.updatedAt
      if (diff < oneDay) {
        today.push(item)
      } else if (diff < 2 * oneDay) {
        yesterday.push(item)
      } else if (diff < 7 * oneDay) {
        last7Days.push(item)
      } else {
        older.push(item)
      }
    })

    return [
      { label: 'Today', items: today },
      { label: 'Yesterday', items: yesterday },
      { label: 'Previous 7 Days', items: last7Days },
      { label: 'Older', items: older },
    ].filter((g) => g.items.length > 0)
  }

  const grouped = groupConversations(filteredConversations)

  const handleStartEdit = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title)
    setMenuOpenId(null)
  }

  const handleSaveEdit = (id: string, e: React.FormEvent) => {
    e.preventDefault()
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim())
    }
    setEditingId(null)
  }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : 'expanded'}`}>
      {/* Sidebar Header */}
      <div className="sidebar-header">
        {!collapsed && (
          <div className="brand-logo">
            <div className="brand-icon-box">
              <img src={revitLogo} alt="RevitAI" className="brand-logo-img" />
            </div>
            <span className="brand-text">RevitAI</span>
          </div>
        )}

        <Tooltip content={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          <button className="icon-btn collapse-btn" onClick={onToggleCollapse}>
            {collapsed ? <PanelLeftOpen className="icon-btn-svg" /> : <PanelLeftClose className="icon-btn-svg" />}
          </button>
        </Tooltip>
      </div>

      {/* New Chat Button */}
      <div className="sidebar-action-container">
        {collapsed ? (
          <Tooltip content="New Chat">
            <button className="new-chat-btn-icon" onClick={onNewChat}>
              <Plus className="btn-plus-icon" />
            </button>
          </Tooltip>
        ) : (
          <button className="new-chat-btn-full" onClick={onNewChat}>
            <Plus className="btn-plus-icon" />
            <span>New Chat</span>
          </button>
        )}
      </div>

      {/* Search Input (Expanded only) */}
      {!collapsed && (
        <div className="sidebar-search-box">
          <Search className="search-icon" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="sidebar-search-input"
          />
        </div>
      )}

      {/* Conversations List */}
      <div className="sidebar-history-list">
        {grouped.length === 0 ? (
          !collapsed && <div className="history-empty-state">No conversations found</div>
        ) : (
          grouped.map((group) => (
            <div key={group.label} className="history-group">
              {!collapsed && <div className="history-group-title">{group.label}</div>}

              {group.items.map((conv) => {
                const isActive = conv.id === activeId

                if (collapsed) {
                  return (
                    <Tooltip key={conv.id} content={conv.title} position="right">
                      <button
                        className={`history-item-collapsed ${isActive ? 'active' : ''}`}
                        onClick={() => onSelectConversation(conv.id)}
                      >
                        <MessageSquare className="history-icon" />
                      </button>
                    </Tooltip>
                  )
                }

                if (editingId === conv.id) {
                  return (
                    <form
                      key={conv.id}
                      className="history-rename-form"
                      onSubmit={(e) => handleSaveEdit(conv.id, e)}
                    >
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        autoFocus
                        onBlur={(e) => handleSaveEdit(conv.id, e)}
                        className="rename-input"
                      />
                    </form>
                  )
                }

                return (
                  <div
                    key={conv.id}
                    className={`history-item ${isActive ? 'active' : ''}`}
                    onClick={() => onSelectConversation(conv.id)}
                  >
                    <MessageSquare className="history-icon" />
                    <span className="history-title" title={conv.title}>
                      {conv.title}
                    </span>

                    <div className="history-actions-menu">
                      <button
                        className="menu-trigger-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          setMenuOpenId(menuOpenId === conv.id ? null : conv.id)
                        }}
                      >
                        <MoreVertical className="menu-icon" />
                      </button>

                      {menuOpenId === conv.id && (
                        <div className="menu-dropdown">
                          <button
                            className="menu-item"
                            onClick={(e) => handleStartEdit(conv, e)}
                          >
                            <Edit2 className="menu-item-icon" />
                            <span>Rename</span>
                          </button>
                          <button
                            className="menu-item text-danger"
                            onClick={(e) => {
                              e.stopPropagation()
                              onDeleteConversation(conv.id)
                              setMenuOpenId(null)
                            }}
                          >
                            <Trash2 className="menu-item-icon" />
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
