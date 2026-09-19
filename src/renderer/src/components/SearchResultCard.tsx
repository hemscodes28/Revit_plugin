import React, { useState } from 'react'
import { ExternalLink, MousePointer, Highlighter, Maximize, Layers, FileText, Box } from 'lucide-react'
import type { SearchResult } from '../utils/storage'

interface SearchResultCardProps {
  result: SearchResult
  isBestMatch?: boolean
  onAction: (result: SearchResult, actionName: string) => Promise<void>
}

export const SearchResultCard: React.FC<SearchResultCardProps> = ({
  result,
  isBestMatch = false,
  onAction,
}) => {
  const [activeAction, setActiveAction] = useState<string | null>(null)

  const resType = (result.result_type || result.type || '').toUpperCase()

  const isElement = resType === 'ELEMENT'
  const isSheet = resType === 'SHEET' || result.view_type === 'DrawingSheet'

  const handleExecuteAction = async (actionName: string) => {
    setActiveAction(actionName)
    try {
      await onAction(result, actionName)
    } finally {
      setActiveAction(null)
    }
  }

  const getBadgeIcon = () => {
    if (isElement) return <Box className="card-badge-icon" />
    if (isSheet) return <FileText className="card-badge-icon" />
    return <Layers className="card-badge-icon" />
  }

  const getTypeLabel = () => {
    if (isElement) return result.category || 'Element'
    if (isSheet) return 'Sheet'
    return result.view_type || 'View'
  }

  return (
    <div className={`result-card ${isBestMatch ? 'primary-result' : ''}`}>
      <div className="card-header">
        <div className="card-header-left">
          <div className="card-badge">
            {getBadgeIcon()}
            <span>{getTypeLabel()}</span>
          </div>
          <h3 className="card-title">{result.name}</h3>
        </div>
        {isBestMatch && <span className="best-match-badge">Best Match</span>}
      </div>

      <p className="card-description">{result.description}</p>

      <div className="card-meta">
        {result.level_name && (
          <div className="meta-item">
            <span className="meta-label">Level</span>
            <span className="meta-value">{result.level_name}</span>
          </div>
        )}

        {(result.revit_view_id != null || result.revit_element_id != null) && (
          <div className="meta-item">
            <span className="meta-label">Revit ID</span>
            <span className="meta-value">{result.revit_view_id ?? result.revit_element_id}</span>
          </div>
        )}

        {result.project_name && (
          <div className="meta-item">
            <span className="meta-label">Project</span>
            <span className="meta-value">{result.project_name}</span>
          </div>
        )}
      </div>

      <div className="card-actions">
        {isElement ? (
          <div className="element-actions-group">
            <button
              className="action-btn secondary-btn"
              disabled={activeAction !== null}
              onClick={() => handleExecuteAction('SELECT')}
            >
              <MousePointer className="btn-icon" />
              <span>{activeAction === 'SELECT' ? 'Selecting...' : 'Select'}</span>
            </button>

            <button
              className="action-btn secondary-btn"
              disabled={activeAction !== null}
              onClick={() => handleExecuteAction('HIGHLIGHT')}
            >
              <Highlighter className="btn-icon" />
              <span>{activeAction === 'HIGHLIGHT' ? 'Highlighting...' : 'Highlight'}</span>
            </button>

            <button
              className="action-btn secondary-btn"
              disabled={activeAction !== null}
              onClick={() => handleExecuteAction('ZOOM')}
            >
              <Maximize className="btn-icon" />
              <span>{activeAction === 'ZOOM' ? 'Zooming...' : 'Zoom'}</span>
            </button>
          </div>
        ) : (
          <button
            className="action-btn primary-btn open-revit-btn"
            disabled={activeAction !== null}
            onClick={() => handleExecuteAction('OPEN')}
          >
            <span>{activeAction === 'OPEN' ? 'Opening in Revit...' : 'Open in Revit'}</span>
            <ExternalLink className="btn-icon-right" />
          </button>
        )}
      </div>
    </div>
  )
}
