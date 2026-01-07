import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatMessage, ChatMessageComponent } from '@/components/Chat/ChatMessage'
import { ProviderSelector } from '@/components/Chat/ProviderSelector'
import { useGenerateSQL, useExecuteSQL, useProviders } from '@/api/nlQuery'

function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('ollama')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: providers = [], isLoading: providersLoading } = useProviders()
  const generateMutation = useGenerateSQL()
  const executeMutation = useExecuteSQL()

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    const assistantMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    }

    setMessages(prev => [...prev, userMessage, assistantMessage])
    setInput('')

    try {
      // Step 1: Generate SQL from natural language
      const sqlResponse = await generateMutation.mutateAsync({
        query: userMessage.content,
        llm_provider: selectedProvider,
      })

      // Step 2: Execute the generated SQL
      const executeResponse = await executeMutation.mutateAsync({
        sql: sqlResponse.sql,
      })

      // Update assistant message with results
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                isLoading: false,
                data: {
                  columns: executeResponse.columns,
                  rows: executeResponse.rows,
                  rowCount: executeResponse.row_count,
                },
              }
            : msg
        )
      )
    } catch (error: any) {
      // Update assistant message with error
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                isLoading: false,
                error: error.response?.data?.detail || error.message || 'Something went wrong',
              }
            : msg
        )
      )
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h2 className="page-header">Chat</h2>
        {!providersLoading && providers.length > 0 && (
          <ProviderSelector
            value={selectedProvider}
            onChange={setSelectedProvider}
            providers={providers}
          />
        )}
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <p className="text-lg mb-2">Ask a question about jobs</p>
            <p className="text-sm">Try: "Show me remote senior engineer jobs" or "Count jobs by location"</p>
          </div>
        )}

        {messages.map(message => (
          <ChatMessageComponent key={message.id} message={message} />
        ))}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="chat-input-container">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question..."
          className="chat-input"
          rows={1}
          disabled={generateMutation.isPending || executeMutation.isPending}
        />
        <Button
          type="submit"
          disabled={!input.trim() || generateMutation.isPending || executeMutation.isPending}
        >
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  )
}

export default ChatPage
