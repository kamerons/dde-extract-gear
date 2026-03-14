import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './index.css';
import App from './App.tsx';
import { ArmorDetailView } from './components/ArmorDetailView.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/armor/:setId" element={<ArmorDetailView />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
