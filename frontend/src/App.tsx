import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { DataSearchPage } from './pages/DataSearchPage';
import { DashboardPage } from './pages/DashboardPage';
import { DatasetsPage } from './pages/DatasetsPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { SettingsPage } from './pages/SettingsPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import { AllProspectsPage } from './pages/AllProspectsPage';
import { RepliesPage } from './pages/RepliesPage';
import { ContactsPage } from './pages/ContactsPage';
import { TasksPage } from './pages/TasksPage';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider, useToast, setToastFunction } from './components/Toast';
import { useEffect } from 'react';

// Component to initialize toast function for API client
function ToastInitializer() {
  const { toast } = useToast();
  useEffect(() => {
    setToastFunction(toast);
  }, [toast]);
  return null;
}

function App() {
  return (
    <ErrorBoundary>
    <ToastProvider>
    <ToastInitializer />
    <BrowserRouter>
      <Routes>
        {/* Data Search - the new homepage */}
        <Route path="/" element={<DataSearchPage />} />
        <Route path="/data-search" element={<DataSearchPage />} />
        
        {/* Companies page - formerly the homepage */}
        <Route path="/companies" element={<HomePage />} />
        
        {/* Company-scoped routes */}
        <Route path="/company/:companyId/*" element={
          <Layout>
            <Routes>
              <Route path="data" element={<DatasetsPage />} />
              <Route path="prospects" element={<AllProspectsPage />} />
              <Route path="knowledge-base" element={<KnowledgeBasePage />} />
              <Route path="replies" element={<RepliesPage />} />
              <Route path="contacts" element={<ContactsPage />} />
              {/* Redirect root to data */}
              <Route path="" element={<Navigate to="data" replace />} />
            </Routes>
          </Layout>
        } />
        
        {/* Global replies page (not company-scoped) */}
        <Route path="/replies" element={
          <Layout>
            <RepliesPage />
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
        
        {/* Tasks page */}
        <Route path="/tasks" element={
          <Layout>
            <TasksPage />
          </Layout>
        } />
        
        {/* Dashboard page */}
        <Route path="/dashboard" element={<DashboardPage />} />
        
        {/* Global CRM contacts page (not company-scoped) */}
        <Route path="/contacts" element={
          <Layout>
            <ContactsPage />
          </Layout>
        } />
        
        {/* Legacy routes - redirect to home */}
        <Route path="/prospects" element={<Navigate to="/" replace />} />
        <Route path="/knowledge-base" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
    </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
