import React from 'react'
import { Sparkles, User } from 'lucide-react'
import type { Message, SearchResult } from '../utils/storage'
import { SearchResultCard } from './SearchResultCard'

interface ChatMessageProps {
  message: Message
  onAction: (result: SearchResult, actionName: string) => Promise<void>
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onAction }) => {
  const isUser = message.role === 'user'

  const hasResults =
    message.results &&
    message.results.length > 0 &&
    (message.type === 'search_results' ||
      message.intent === 'REVIT_SEARCH' ||
      message.intent === 'REVIT_ACTION' ||
      message.intent === 'FOLLOW_UP')

  return (
    <div className={`message ${isUser ? 'user-message' : 'assistant-message'}`}>
      <div className={`avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? <User className="avatar-icon" /> : <Sparkles className="avatar-icon" />}
      </div>

      <div className="message-body">
        <div className="message-header">
          <span className="sender-name">{isUser ? 'You' : 'RevitAI'}</span>
          <span className="timestamp">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>

        <div className="message-content">{message.content}</div>

        {hasResults && (
          <div className="results-container">
            {message.results!.map((result, idx) => (
              <SearchResultCard
                key={`${result.revit_view_id || result.revit_element_id || result.name}-${idx}`}
                result={result}
                isBestMatch={idx === 0}
                onAction={onAction}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
