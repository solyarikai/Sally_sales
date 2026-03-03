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
import PromptDebugPage from './pages/PromptDebugPage';
import { ContactsPage } from './pages/ContactsPage';
import { ContactDetailPage } from './pages/ContactDetailPage';
import { TasksPage } from './pages/TasksPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { SearchResultsPage } from './pages/SearchResultsPage';
import { PipelinePage } from './pages/PipelinePage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectPage } from './pages/ProjectPage';
import { ProjectKnowledgePage } from './pages/ProjectKnowledgePage';
import { ProjectChatPage } from './pages/ProjectChatPage';
import { QueryDashboardPage } from './pages/QueryDashboardPage';
import { OperatorActionsPage } from './pages/OperatorActionsPage';
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
        <Route path="/" element={<Layout><DataSearchPage /></Layout>} />
        <Route path="/data-search" element={<Layout><DataSearchPage /></Layout>} />
        
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
        
        {/* Redirect standalone /replies to unified /tasks/replies */}
        <Route path="/replies" element={<Navigate to="/tasks/replies" replace />} />

        {/* Shared routes (templates and settings) - not company-scoped */}
        <Route path="/prompt-debug" element={
          <Layout>
            <PromptDebugPage />
          </Layout>
        } />
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
        
        {/* Tasks page — route-based tabs */}
        <Route path="/tasks" element={<Navigate to="/tasks/replies" replace />} />
        <Route path="/tasks/:tab" element={
          <Layout>
            <TasksPage />
          </Layout>
        } />

        {/* Knowledge page — ICP, templates, learning logs */}
        <Route path="/knowledge" element={<Navigate to="/knowledge/icp" replace />} />
        <Route path="/knowledge/:tab" element={
          <Layout>
            <KnowledgePage />
          </Layout>
        } />

        {/* Operator Actions page */}
        <Route path="/actions" element={
          <Layout>
            <OperatorActionsPage />
          </Layout>
        } />
        
        {/* Dashboard page */}
        <Route path="/dashboard" element={<DashboardPage />} />
        
        {/* Search Results */}
        <Route path="/search-results" element={
          <Layout>
            <SearchResultsPage />
          </Layout>
        } />
        <Route path="/search-results/:jobId" element={
          <Layout>
            <SearchResultsPage />
          </Layout>
        } />

        {/* Pipeline */}
        <Route path="/pipeline" element={
          <Layout>
            <PipelinePage />
          </Layout>
        } />

        {/* Query Dashboard */}
        <Route path="/dashboard/queries" element={
          <Layout>
            <QueryDashboardPage />
          </Layout>
        } />

        {/* Projects management */}
        <Route path="/projects" element={
          <Layout>
            <ProjectsPage />
          </Layout>
        } />
        <Route path="/projects/:id" element={
          <Layout>
            <ProjectPage />
          </Layout>
        } />
        <Route path="/projects/:projectId/knowledge" element={
          <Layout>
            <ProjectKnowledgePage />
          </Layout>
        } />
        <Route path="/projects/:projectId/chat" element={
          <Layout>
            <ProjectChatPage />
          </Layout>
        } />

        {/* Contact detail page (shareable URL) */}
        <Route path="/contacts/:contactId" element={
          <Layout>
            <ContactDetailPage />
          </Layout>
        } />

        {/* Legacy routes — redirect to unified tasks page */}
        <Route path="/operator-tasks" element={<Navigate to="/tasks/replies" replace />} />

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
