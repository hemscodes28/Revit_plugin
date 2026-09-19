import React from 'react'
import { Sparkles } from 'lucide-react'

export const TypingIndicator: React.FC = () => {
  return (
    <div className="message assistant-message typing-indicator-container">
      <div className="avatar assistant-avatar">
        <Sparkles className="avatar-icon" />
      </div>
      <div className="message-body">
        <div className="message-header">
          <span className="sender-name">RevitAI</span>
        </div>
        <div className="typing-box">
          <span className="typing-text">RevitAI is thinking</span>
          <div className="typing-dots">
            <span className="dot dot-1" />
            <span className="dot dot-2" />
            <span className="dot dot-3" />
          </div>
        </div>
      </div>
    </div>
  )
}
