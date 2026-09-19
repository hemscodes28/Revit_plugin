import React from 'react'
import { PanelLeft, Plus, Trash2, FolderCheck, Wifi, WifiOff } from 'lucide-react'
import { Tooltip } from './Tooltip'
import revitLogo from '../assets/revit-logo.png'

interface ChatHeaderProps {
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
  activeProjectName: string | null
  isConnected: boolean
  onNewChat: () => void
  onClearChat: () => void
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  sidebarCollapsed,
  onToggleSidebar,
  activeProjectName,
  isConnected,
  onNewChat,
  onClearChat,
}) => {
  return (
    <header className="app-header">
      <div className="header-left">
        <Tooltip content={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          <button className="icon-btn header-toggle-btn" onClick={onToggleSidebar}>
            <PanelLeft className="icon-btn-svg" />
          </button>
        </Tooltip>

        {sidebarCollapsed && (
          <div className="brand-logo-inline">
            <div className="brand-icon-box">
              <img src={revitLogo} alt="RevitAI" className="brand-logo-img" />
            </div>
            <span className="brand-text">RevitAI</span>
          </div>
        )}
      </div>

      <div className="header-center">
        <div className="project-badge">
          <FolderCheck className="badge-project-icon" />
          <div className="project-info-text">
            <span className="badge-caption">Current Project</span>
            <span className="badge-title">
              {activeProjectName || 'No Active Project'}
            </span>
          </div>
        </div>
      </div>

      <div className="header-right">
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? <Wifi className="status-icon" /> : <WifiOff className="status-icon" />}
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>

        <div className="header-actions">
          <Tooltip content="New chat">
            <button className="icon-btn" onClick={onNewChat}>
              <Plus className="icon-btn-svg" />
            </button>
          </Tooltip>

          <Tooltip content="Clear conversation">
            <button className="icon-btn text-danger" onClick={onClearChat}>
              <Trash2 className="icon-btn-svg" />
            </button>
          </Tooltip>
        </div>
      </div>
    </header>
  )
}
