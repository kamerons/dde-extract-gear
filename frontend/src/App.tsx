import { useState } from 'react';
import { InitialConfiguration } from './components/InitialConfiguration';
import { ResultsScreen } from './components/ResultsScreen';
import { ExtractConfig } from './components/ExtractConfig';
import type { BuildPreferences } from './types';
import './App.css';

type View = 'configuration' | 'results';
type Tab = 'recommendations' | 'configuration';

function App() {
  const [currentView, setCurrentView] = useState<View>('configuration');
  const [activeTab, setActiveTab] = useState<Tab>('recommendations');
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
          className={`app-tab ${activeTab === 'configuration' ? 'app-tab-active' : ''}`}
          onClick={() => setActiveTab('configuration')}
          aria-current={activeTab === 'configuration' ? 'page' : undefined}
        >
          Configuration
        </button>
      </nav>
      <main className="app-tab-panel">
        {activeTab === 'recommendations' && (
          <InitialConfiguration
            onNavigateToResults={handleNavigateToResults}
            onError={setConfigError}
            error={configError}
          />
        )}
        {activeTab === 'configuration' && <ExtractConfig />}
      </main>
    </div>
  );
}

export default App;
