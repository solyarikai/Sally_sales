import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider, useToast, setToastFunction } from './components/Toast';
import { lazy, Suspense, useEffect } from 'react';

// ---------------------------------------------------------------------------
// Lazy-loaded pages — each becomes its own chunk, loaded on first navigation.
// Named exports use .then(m => ({ default: m.X })) adapter for React.lazy().
// ---------------------------------------------------------------------------
const DataSearchPage = lazy(() => import('./pages/DataSearchPage').then(m => ({ default: m.DataSearchPage })));
const HomePage = lazy(() => import('./pages/HomePage').then(m => ({ default: m.HomePage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const DatasetsPage = lazy(() => import('./pages/DatasetsPage').then(m => ({ default: m.DatasetsPage })));
const TemplatesPage = lazy(() => import('./pages/TemplatesPage').then(m => ({ default: m.TemplatesPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const KnowledgeBasePage = lazy(() => import('./pages/KnowledgeBasePage'));
const AllProspectsPage = lazy(() => import('./pages/AllProspectsPage').then(m => ({ default: m.AllProspectsPage })));
const RepliesPage = lazy(() => import('./pages/RepliesPage').then(m => ({ default: m.RepliesPage })));
const PromptDebugPage = lazy(() => import('./pages/PromptDebugPage'));
const ContactsPage = lazy(() => import('./pages/ContactsPage').then(m => ({ default: m.ContactsPage })));
const ContactDetailPage = lazy(() => import('./pages/ContactDetailPage').then(m => ({ default: m.ContactDetailPage })));
const TasksPage = lazy(() => import('./pages/TasksPage').then(m => ({ default: m.TasksPage })));
const KnowledgePage = lazy(() => import('./pages/KnowledgePage').then(m => ({ default: m.KnowledgePage })));
const SearchResultsPage = lazy(() => import('./pages/SearchResultsPage').then(m => ({ default: m.SearchResultsPage })));
const PipelinePage = lazy(() => import('./pages/PipelinePage').then(m => ({ default: m.PipelinePage })));
const ProjectsPage = lazy(() => import('./pages/ProjectsPage').then(m => ({ default: m.ProjectsPage })));
const ProjectPage = lazy(() => import('./pages/ProjectPage').then(m => ({ default: m.ProjectPage })));
const ProjectKnowledgePage = lazy(() => import('./pages/ProjectKnowledgePage').then(m => ({ default: m.ProjectKnowledgePage })));
const ProjectChatPage = lazy(() => import('./pages/ProjectChatPage').then(m => ({ default: m.ProjectChatPage })));
const QueryDashboardPage = lazy(() => import('./pages/QueryDashboardPage').then(m => ({ default: m.QueryDashboardPage })));
const OperatorActionsPage = lazy(() => import('./pages/OperatorActionsPage').then(m => ({ default: m.OperatorActionsPage })));
const GodPanelPage = lazy(() => import('./pages/GodPanelPage').then(m => ({ default: m.GodPanelPage })));
const TelegramInboxPage = lazy(() => import('./pages/TelegramInboxPage').then(m => ({ default: m.TelegramInboxPage })));
const TelegramOutreachPage = lazy(() => import('./pages/TelegramOutreachPage').then(m => ({ default: m.TelegramOutreachPage })));

// Minimal loading spinner — shown while a lazy chunk downloads
function PageLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin opacity-40" />
    </div>
  );
}

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
      <Suspense fallback={<PageLoader />}>
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

        {/* Reply Intelligence — redirect to Knowledge sub-tab */}
        <Route path="/intelligence" element={<Navigate to="/knowledge/intelligence" replace />} />

        {/* God Panel — campaign intelligence */}
        <Route path="/god-panel" element={
          <Layout>
            <GodPanelPage />
          </Layout>
        } />

        {/* Telegram Outreach — tab-based */}
        <Route path="/telegram-outreach" element={<Navigate to="/telegram-outreach/info" replace />} />
        <Route path="/telegram-outreach/:tab" element={
          <Layout>
            <TelegramOutreachPage />
          </Layout>
        } />

        {/* Legacy Telegram Inbox redirect */}
        <Route path="/telegram-inbox" element={<Navigate to="/telegram-outreach/inbox" replace />} />

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
      </Suspense>
    </BrowserRouter>
    </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
