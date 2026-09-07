function App() {
  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>RevitAI</h1>
          <span>AI Assistant for Autodesk Revit</span>
        </div>
      </header>

      <main className="content">
        <div className="welcome">
          <h2>Welcome to RevitAI</h2>

          <p>
            Ask me to find Revit files, views, plans, or project information.
          </p>

          <div className="example">
            <strong>Try asking:</strong>

            <p>
              "Find the hospital ground floor plan"
            </p>
          </div>
        </div>
      </main>

      <footer className="input-area">
        <input
          type="text"
          placeholder="Ask RevitAI..."
        />

        <button>Send</button>
      </footer>
    </div>
  )
}

export default App