import { Loader2, AlertCircle } from 'lucide-react'
import { MetricCard } from './MetricCard'
import { ResultTable } from './ResultTable'

export interface ChatMessageData {
  columns: string[]
  rows: Record<string, any>[]
  rowCount: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  data?: ChatMessageData
  isLoading?: boolean
  error?: string
}

interface ChatMessageProps {
  message: ChatMessage
}

function isSingleValue(data: ChatMessageData): boolean {
  return data.columns.length === 1 && data.rows.length === 1
}

export function ChatMessageComponent({ message }: ChatMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="chat-message user-message">
        <div className="message-content">
          <span className="message-label">You</span>
          <p>{message.content}</p>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="chat-message assistant-message">
      <div className="message-content">
        <span className="message-label">Assistant</span>

        {message.isLoading && (
          <div className="loading-indicator">
            <Loader2 className="animate-spin w-4 h-4" />
            <span>Thinking...</span>
          </div>
        )}

        {message.error && (
          <div className="error-message">
            <AlertCircle className="inline-block w-4 h-4 mr-2" />
            {message.error}
          </div>
        )}

        {message.data && (
          <>
            {isSingleValue(message.data) ? (
              <MetricCard data={message.data} />
            ) : (
              <ResultTable data={message.data} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
