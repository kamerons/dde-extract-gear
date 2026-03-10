import { useState } from 'react';
import { InitialConfiguration } from './components/InitialConfiguration';
import { ResultsScreen } from './components/ResultsScreen';
import { ExtractTraining } from './components/ExtractTraining';
import type { BuildPreferences } from './types';
import './App.css';

type View = 'configuration' | 'results';
type Tab = 'recommendations' | 'training';

function App() {
  const [currentView, setCurrentView] = useState<View>('configuration');
  const [activeTab, setActiveTab] = useState<Tab>('training');
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
    <div className="app-with-tabs">
      <nav className="app-tabs" aria-label="Main">
        <button
          type="button"
          className={`app-tab ${activeTab === 'recommendations' ? 'app-tab-active' : ''}`}
          onClick={() => setActiveTab('recommendations')}
          aria-current={activeTab === 'recommendations' ? 'page' : undefined}
        >
          Recommendations
        </button>
        <button
          type="button"
          className={`app-tab ${activeTab === 'training' ? 'app-tab-active' : ''}`}
          onClick={() => setActiveTab('training')}
          aria-current={activeTab === 'training' ? 'page' : undefined}
        >
          Training
        </button>
      </nav>
      <main
        className={`app-tab-panel${activeTab === 'training' ? ' app-tab-panel--training' : ''}`}
      >
        {activeTab === 'recommendations' && (
          <InitialConfiguration
            onNavigateToResults={handleNavigateToResults}
            onError={setConfigError}
            error={configError}
          />
        )}
        {activeTab === 'training' && <ExtractTraining />}
      </main>
    </div>
  );
}

export default App;
