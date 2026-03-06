import { useState } from 'react';
import { InitialConfiguration } from './components/InitialConfiguration';
import { ResultsScreen } from './components/ResultsScreen';
import type { BuildPreferences } from './types';
import './App.css';

type View = 'configuration' | 'results';

function App() {
  const [currentView, setCurrentView] = useState<View>('configuration');
  const [pendingPreferences, setPendingPreferences] = useState<BuildPreferences | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  const handleNavigateToResults = (preferences: BuildPreferences) => {
    setConfigError(null);
    setPendingPreferences(preferences);
    setCurrentView('results');
  };

  const handleBackToConfiguration = () => {
    setPendingPreferences(null);
    setCurrentView('configuration');
  };

  if (currentView === 'results' && pendingPreferences) {
    return (
      <ResultsScreen
        initialPreferences={pendingPreferences}
        onBack={handleBackToConfiguration}
      />
    );
  }

  return (
    <InitialConfiguration
      onNavigateToResults={handleNavigateToResults}
      onError={setConfigError}
      error={configError}
    />
  );
}

export default App;
