import { useState } from 'react';
import { InitialConfiguration } from './components/InitialConfiguration';
import { ResultsScreen } from './components/ResultsScreen';
import type { Recommendation } from './types';
import './App.css';

type View = 'configuration' | 'results';

function App() {
  const [currentView, setCurrentView] = useState<View>('configuration');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePreferencesSubmitted = async (recommendationsData: Recommendation[]) => {
    setRecommendations(recommendationsData);
    setError(null);
    setCurrentView('results');
  };

  const handleBackToConfiguration = () => {
    setCurrentView('configuration');
    setError(null);
  };

  if (currentView === 'results') {
    return (
      <ResultsScreen
        recommendations={recommendations}
        onBack={handleBackToConfiguration}
        isLoading={isLoading}
        error={error}
      />
    );
  }

  return (
    <InitialConfiguration
      onPreferencesSubmitted={handlePreferencesSubmitted}
      onLoadingChange={setIsLoading}
      onError={setError}
    />
  );
}

export default App;
