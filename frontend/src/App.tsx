import { useState } from 'react';
import { InitialConfiguration } from './components/InitialConfiguration';
import { ResultsScreen } from './components/ResultsScreen';
import { ExtractTraining } from './components/ExtractTraining';
import { ExtractVerification } from './components/ExtractVerification';
import type { BuildPreferences } from './types';
import './App.css';

type View = 'configuration' | 'results';
type Tab = 'recommendations' | 'training' | 'verification';

function App() {
  const [currentView, setCurrentView] = useState<View>('configuration');
  const [activeTab, setActiveTab] = useState<Tab>('training');
  const [pendingPreferences, setPendingPreferences] = useState<BuildPreferences | null>(null);
  const [pendingDataFile, setPendingDataFile] = useState<string | undefined>(undefined);
  const [configError, setConfigError] = useState<string | null>(null);

  const handleNavigateToResults = (preferences: BuildPreferences, dataFile?: string) => {
    setConfigError(null);
    setPendingPreferences(preferences);
    setPendingDataFile(dataFile);
    setCurrentView('results');
  };

  const handleBackToConfiguration = () => {
    setPendingPreferences(null);
    setPendingDataFile(undefined);
    setCurrentView('configuration');
  };

  if (currentView === 'results' && pendingPreferences) {
    return (
      <ResultsScreen
        initialPreferences={pendingPreferences}
        initialDataFile={pendingDataFile}
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
        <button
          type="button"
          className={`app-tab ${activeTab === 'verification' ? 'app-tab-active' : ''}`}
          onClick={() => setActiveTab('verification')}
          aria-current={activeTab === 'verification' ? 'page' : undefined}
        >
          Verification
        </button>
      </nav>
      <main
        className={`app-tab-panel${activeTab === 'training' ? ' app-tab-panel--training' : ''}${activeTab === 'verification' ? ' app-tab-panel--verification' : ''}`}
      >
        {activeTab === 'recommendations' && (
          <InitialConfiguration
            onNavigateToResults={handleNavigateToResults}
            onError={setConfigError}
            error={configError}
          />
        )}
        {activeTab === 'training' && <ExtractTraining />}
        {activeTab === 'verification' && <ExtractVerification />}
      </main>
    </div>
  );
}

export default App;
