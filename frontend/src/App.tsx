import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { DatasetsPage } from './pages/DatasetsPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { SettingsPage } from './pages/SettingsPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { AllProspectsPage } from './pages/AllProspectsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Home page - company selection */}
        <Route path="/" element={<HomePage />} />
        
        {/* Company-scoped routes */}
        <Route path="/company/:companyId/*" element={
          <Layout>
            <Routes>
              <Route path="data" element={<DatasetsPage />} />
              <Route path="prospects" element={<AllProspectsPage />} />
              <Route path="knowledge-base" element={<KnowledgeBasePage />} />
              {/* Redirect root to data */}
              <Route path="" element={<Navigate to="data" replace />} />
            </Routes>
          </Layout>
        } />
        
        {/* Shared routes (templates and settings) - not company-scoped */}
        <Route path="/templates" element={
          <Layout>
            <TemplatesPage />
          </Layout>
        } />
        <Route path="/settings" element={
          <Layout>
            <SettingsPage />
          </Layout>
        } />
        
        {/* Legacy routes - redirect to home */}
        <Route path="/prospects" element={<Navigate to="/" replace />} />
        <Route path="/knowledge-base" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
