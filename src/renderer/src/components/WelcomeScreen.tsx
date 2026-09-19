import React from 'react'
import revitLogo from '../assets/revit-logo.png'

interface WelcomeScreenProps {
  onSelectSuggestion?: (query: string) => void
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = () => {
  return (
    <div className="welcome-screen">
      <div className="welcome-hero">
        <div className="welcome-logo-badge">
          <img src={revitLogo} alt="RevitAI Logo" className="hero-logo-img" />
        </div>
        <h2 className="welcome-title">RevitAI</h2>
        <p className="welcome-subtitle">
          Your intelligent assistant for Autodesk Revit. Find views, sheets, levels, and model elements using natural language.
        </p>
      </div>
    </div>
  )
}
