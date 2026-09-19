import { useState } from 'react'


// ============================================================
// TYPES
// ============================================================

interface SearchResult {
  type: string
  name: string
  description: string
  action: string
  revit_view_id?: number
  project_id?: number
  project_name?: string
  file_path?: string
  view_type?: string
  level_name?: string
}

interface ChatResponse {
  response: string
  results: SearchResult[]
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  results?: SearchResult[]
}


// ============================================================
// APP
// ============================================================

function App() {

  const [message, setMessage] = useState('')

  const [messages, setMessages] = useState<Message[]>([])

  const [loading, setLoading] = useState(false)

  const [error, setError] = useState('')


  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  const sendMessage = async () => {

    const trimmedMessage = message.trim()

    if (!trimmedMessage) {
      return
    }

    if (loading) {
      return
    }


    // --------------------------------------------------------
    // Add user message
    // --------------------------------------------------------

    setMessages((previousMessages) => [
      ...previousMessages,
      {
        role: 'user',
        content: trimmedMessage,
      },
    ])


    // --------------------------------------------------------
    // Clear input
    // --------------------------------------------------------

    setMessage('')

    setError('')

    setLoading(true)


    try {

      // ------------------------------------------------------
      // Send request to FastAPI
      // ------------------------------------------------------

      const response = await fetch(
        'http://127.0.0.1:8000/chat',
        {
          method: 'POST',

          headers: {
            'Content-Type': 'application/json',
          },

          body: JSON.stringify({
            message: trimmedMessage,
          }),
        },
      )


      // ------------------------------------------------------
      // HTTP error
      // ------------------------------------------------------

      if (!response.ok) {

        throw new Error(
          `Backend returned HTTP ${response.status}`,
        )
      }


      // ------------------------------------------------------
      // Parse JSON
      // ------------------------------------------------------

      const data: ChatResponse =
        await response.json()


      // ------------------------------------------------------
      // Add assistant response
      // ------------------------------------------------------

      setMessages((previousMessages) => [
        ...previousMessages,
        {
          role: 'assistant',
          content: data.response,
          results: data.results,
        },
      ])

    } catch (requestError) {

      console.error(
        'Chat request failed:',
        requestError,
      )


      const errorMessage =
        requestError instanceof Error
          ? requestError.message
          : 'Unknown error'


      setError(
        `Unable to connect to RevitAI backend. ${errorMessage}`,
      )


      setMessages((previousMessages) => [
        ...previousMessages,
        {
          role: 'assistant',
          content:
            'I could not connect to the RevitAI backend.',
        },
      ])

    } finally {

      setLoading(false)
    }
  }


  // ==========================================================
  // OPEN REVIT RESULT (Explicitly sends action = 'OPEN')
  // ==========================================================

  const openResult = async (
    result: SearchResult,
    overrideAction: string = 'OPEN',
  ) => {

    try {

      const payload = {
        ...result,
        action: overrideAction,
      }

      console.log(
        'Executing Revit action:',
        payload,
      )


      const response =
        await window.electronAPI.openRevitResult(
          payload,
        )


      console.log(
        'Revit response:',
        response,
      )


      if (!response.success) {

        setError(
          response.message,
        )

        return
      }


      setError('')

    } catch (openError) {

      console.error(
        'Failed to execute Revit action:',
        openError,
      )


      setError(
        'Could not communicate with the Revit plugin.',
      )
    }
  }


  // ==========================================================
  // HANDLE ENTER KEY
  // ==========================================================

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
  ) => {

    if (
      event.key === 'Enter'
      && !event.shiftKey
    ) {

      event.preventDefault()

      sendMessage()
    }
  }


  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <div className="app">

      {/* ================================================== */}
      {/* HEADER */}
      {/* ================================================== */}

      <header className="header">

        <div>

          <h1>
            RevitAI
          </h1>

          <p>
            AI Assistant for Autodesk Revit
          </p>

        </div>

        <div className="status">

          <span className="status-dot" />

          Backend Connected

        </div>

      </header>


      {/* ================================================== */}
      {/* CHAT AREA */}
      {/* ================================================== */}

      <main className="chat-area">

        {/* ------------------------------------------------ */}
        {/* Empty state */}
        {/* ------------------------------------------------ */}

        {messages.length === 0 && (

          <div className="welcome">

            <h2>
              How can I help you?
            </h2>

            <p>
              Search your Revit project using natural language.
            </p>

            <div className="examples">

              <button
                onClick={() => {
                  setMessage(
                    'Open L1',
                  )
                }}
              >
                Open L1
              </button>

              <button
                onClick={() => {
                  setMessage(
                    'Show me the first floor plan',
                  )
                }}
              >
                First floor plan
              </button>

              <button
                onClick={() => {
                  setMessage(
                    'Show me the 3D view',
                  )
                }}
              >
                3D View
              </button>

            </div>

          </div>

        )}


        {/* ------------------------------------------------ */}
        {/* Messages */}
        {/* ------------------------------------------------ */}

        {messages.map(
          (chatMessage, messageIndex) => (

            <div
              key={messageIndex}
              className={
                chatMessage.role === 'user'
                  ? 'message user-message'
                  : 'message assistant-message'
              }
            >

              <div className="message-label">

                {chatMessage.role === 'user'
                  ? 'You'
                  : 'RevitAI'}

              </div>


              <div className="message-content">

                {chatMessage.content}

              </div>


              {/* ------------------------------------------ */}
              {/* Search Results */}
              {/* ------------------------------------------ */}

              {chatMessage.results &&
                chatMessage.results.length > 0 && (

                <div className="results">

                  {chatMessage.results.map(
                    (result, resultIndex) => (

                      <div
                        key={`${result.revit_view_id || result.name}-${resultIndex}`}
                        className={
                          resultIndex === 0
                            ? 'result-card primary-result'
                            : 'result-card'
                        }
                      >

                        <div className="result-header">

                          <div>

                            <h3>
                              {result.name}
                            </h3>

                            <span className="result-type">
                              {result.type}
                            </span>

                          </div>

                          {resultIndex === 0 && (

                            <span className="best-match">
                              Best Match
                            </span>

                          )}

                        </div>


                        <p className="result-description">

                          {result.description}

                        </p>


                        <div className="result-meta">

                          {result.revit_view_id !== undefined && (
                            <span>
                              Revit ID: {result.revit_view_id}
                            </span>
                          )}

                          {result.project_name ? (
                            <span>
                              Project: {result.project_name}
                            </span>
                          ) : result.project_id ? (
                            <span>
                              Project ID: {result.project_id}
                            </span>
                          ) : null}

                        </div>


                        <button
                          className="open-button"
                          onClick={() =>
                            openResult(result, 'OPEN')
                          }
                        >
                          Open in Revit
                        </button>

                      </div>

                    ),
                  )}

                </div>

              )}

            </div>

          ),
        )}


        {/* ------------------------------------------------ */}
        {/* Loading */}
        {/* ------------------------------------------------ */}

        {loading && (

          <div className="message assistant-message">

            <div className="message-label">
              RevitAI
            </div>

            <div className="loading">

              Searching your Revit project...

            </div>

          </div>

        )}

      </main>


      {/* ================================================== */}
      {/* ERROR */}
      {/* ================================================== */}

      {error && (

        <div className="error-message">

          {error}

        </div>

      )}


      {/* ================================================== */}
      {/* INPUT */}
      {/* ================================================== */}

      <footer className="input-area">

        <input
          type="text"
          value={message}
          onChange={(event) =>
            setMessage(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder="Ask RevitAI something..."
          disabled={loading}
        />

        <button
          onClick={sendMessage}
          disabled={
            loading
            || !message.trim()
          }
        >
          {loading
            ? 'Searching...'
            : 'Send'}
        </button>

      </footer>

    </div>
  )
}


export default App