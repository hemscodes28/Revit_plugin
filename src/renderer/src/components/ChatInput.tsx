import React, { useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { Tooltip } from './Tooltip'

interface ChatInputProps {
  value: string
  onChange: (val: string) => void
  onSend: () => void
  loading: boolean
}

export const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSend,
  loading,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !loading) {
        onSend()
      }
    }
  }

  return (
    <footer className="input-area-wrapper">
      <div className="input-container">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask RevitAI anything about views, sheets, or model elements..."
          disabled={loading}
          className="chat-textarea"
        />

        <Tooltip content="Send message (Enter)">
          <button
            className="send-circular-btn"
            onClick={onSend}
            disabled={loading || !value.trim()}
          >
            <Send className="send-icon" />
          </button>
        </Tooltip>
      </div>

      <div className="input-footer-caption">
        Press <kbd>Enter</kbd> to send • <kbd>Shift</kbd> + <kbd>Enter</kbd> for new line
      </div>
    </footer>
  )
}
