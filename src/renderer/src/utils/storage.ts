export interface SearchResult {
  type: string
  result_type?: string
  name: string
  description: string
  action: string
  revit_view_id?: number
  revit_element_id?: number
  project_id?: number
  project_name?: string
  file_path?: string
  view_type?: string
  level_name?: string
  category?: string
  family_name?: string
  type_name?: string
  score?: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  type?: string
  intent?: string
  results?: SearchResult[]
}

export interface Conversation {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: Message[]
}

const STORAGE_KEY = 'revitai_conversations_v2'
const ACTIVE_ID_KEY = 'revitai_active_conv_id_v2'

export function generateTitleFromQuery(query: string): string {
  if (!query) return 'New Chat'
  const trimmed = query.trim()

  const lower = trimmed.toLowerCase()
  if (lower.includes('project') || lower.includes('model') || lower.includes('file')) {
    if (lower.includes('what') || lower.includes('which') || lower.includes('info')) {
      return 'Current Project Info'
    }
  }

  // Alphanumeric code or level match (e.g. L3, S100)
  const levelMatch = trimmed.match(/\b(L\d|Level\s*\d+|S\d{3}|A\d{3})\b/i)
  const levelStr = levelMatch ? levelMatch[0].toUpperCase() : ''

  if (lower.includes('floor plan') || lower.includes('flloor plan')) {
    return levelStr ? `${levelStr} Floor Plans` : 'Floor Plans'
  }
  if (lower.includes('structural plan')) {
    return levelStr ? `${levelStr} Structural Plans` : 'Structural Plans'
  }
  if (lower.includes('structural schedule') || lower.includes('schedule')) {
    return 'Structural Schedules'
  }
  if (lower.includes('ceiling')) {
    return levelStr ? `${levelStr} Ceiling Plans` : 'Ceiling Plans'
  }
  if (lower.includes('3d')) {
    return '3D Model View'
  }
  if (lower.includes('elevation')) {
    return 'Elevations'
  }
  if (lower.includes('section')) {
    return 'Building Sections'
  }
  if (lower.includes('wall')) {
    return levelStr ? `${levelStr} Wall Search` : 'Wall Elements'
  }
  if (lower.includes('door')) {
    return levelStr ? `${levelStr} Door Search` : 'Door Elements'
  }
  if (lower.includes('sheet') || lower.includes('s100')) {
    return levelStr ? `Sheet ${levelStr}` : 'Drawing Sheets'
  }

  // Fallback: capitalize first few meaningful words (up to 4 words)
  const cleanWords = trimmed
    .replace(/^(show me|find me|open|search for|please|get|display)\s+/i, '')
    .split(/\s+/)
    .slice(0, 4)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')

  return cleanWords.length > 2 ? cleanWords : 'New Conversation'
}

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    return parsed
      .filter((c) => c && typeof c === 'object' && c.id && Array.isArray(c.messages))
      .sort((a, b) => b.updatedAt - a.updatedAt)
  } catch (err) {
    console.error('Error loading conversations from localStorage:', err)
    return []
  }
}

export function saveConversations(conversations: Conversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
  } catch (err) {
    console.error('Error saving conversations to localStorage:', err)
  }
}

export function loadActiveId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_ID_KEY)
  } catch (err) {
    return null
  }
}

export function saveActiveId(id: string | null): void {
  try {
    if (id) {
      localStorage.setItem(ACTIVE_ID_KEY, id)
    } else {
      localStorage.removeItem(ACTIVE_ID_KEY)
    }
  } catch (err) {
    console.error('Error saving active conversation ID:', err)
  }
}

export function createNewConversation(): Conversation {
  const now = Date.now()
  return {
    id: `conv_${now}_${Math.random().toString(36).substring(2, 7)}`,
    title: 'New Chat',
    createdAt: now,
    updatedAt: now,
    messages: [],
  }
}
