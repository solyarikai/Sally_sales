import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Send,
  X,
  Building2,
  Globe,
  Users,
  MapPin,
  ThumbsUp,
  ThumbsDown,
  Download,
  Sparkles,
  Layers,
  ExternalLink,
  Loader2,
  Zap,
  Target,
  BarChart3,
  Bot,
  ArrowRight,
  RefreshCw,
  Filter,
  Check,
  Plus,
  Trash2,
  GitCompareArrows,
  MessageSquare,
  Lightbulb,
  ShieldCheck,
  AlertTriangle,
  Info,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  StopCircle,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronDown,
  Eye,
  EyeOff,
} from 'lucide-react';
import { cn } from '../lib/utils';
import type { SearchFilter, CompanyResult, ChatMessage, ExtractedPattern, VerificationCriteria, SearchProgressEvent, SearchResultItem, SpendingInfo } from '../api/dataSearch';
import { dataSearchApi, projectSearchApi } from '../api/dataSearch';
import { contactsApi, type Project } from '../api/contacts';
import { pipelineApi } from '../api/pipeline';

// Search modes
type SearchMode = 'chat' | 'reverse' | 'project';

// Pipeline stage for project search (used by cache and handlers)
type PipelineStage = 'idle' | 'searching' | 'search_done' | 'contacts' | 'contacts_done' | 'enrichment' | 'done';
interface AutoEnrichConfig {
  auto_extract?: boolean;
  auto_apollo?: boolean;
  max_people?: number;
  titles?: string[];
  max_credits?: number;
}

// Chat message for project search (extended with system role)
interface ProjectChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

// Example queries for inspiration
const EXAMPLE_QUERIES = [
  { text: 'SaaS companies in Germany with 50-200 employees', icon: Building2 },
  { text: 'Fintech startups in London founded after 2020', icon: Zap },
  { text: 'E-commerce companies using Shopify in the US', icon: BarChart3 },
  { text: 'Healthcare tech companies with Series A funding', icon: Target },
];

// Web search examples (for project/chat mode)
const WEB_SEARCH_EXAMPLES = [
  { text: 'Find villa builders in Dubai and Abu Dhabi', icon: Building2 },
  { text: 'Construction companies in UAE specializing in luxury villas', icon: Target },
  { text: 'Family offices in Moscow managing private wealth', icon: Zap },
  { text: 'Architecture firms in Dubai with villa portfolio', icon: Globe },
];

// Example company for reverse engineering
interface ExampleCompany {
  id: string;
  name: string;
  domain?: string;
  industry?: string;
  employee_count?: string;
  location?: string;
  technologies?: string[];
}

// Animated gradient background component
function AnimatedBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute -top-40 -right-40 w-96 h-96 bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-gradient-to-tr from-blue-500/10 to-cyan-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-radial from-white/50 to-transparent rounded-full" />
    </div>
  );
}

// Typing animation component
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-3 py-2">
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  );
}

// Animated text component for AI responses
function TypewriterText({ text, onComplete }: { text: string; onComplete?: () => void }) {
  const [displayText, setDisplayText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (text.length === 0) return;
    
    let index = 0;
    const interval = setInterval(() => {
      if (index < text.length) {
        setDisplayText(text.slice(0, index + 1));
        index++;
      } else {
        clearInterval(interval);
        setIsComplete(true);
        onComplete?.();
      }
    }, 15); // 15ms per character for smooth typing

    return () => clearInterval(interval);
  }, [text, onComplete]);

  return (
    <span>
      {displayText}
      {!isComplete && <span className="inline-block w-0.5 h-4 bg-indigo-500 ml-0.5 animate-pulse" />}
    </span>
  );
}

// Filter chip component with animation
function FilterChip({ filter, onRemove, index }: { filter: SearchFilter; onRemove: () => void; index: number }) {
  return (
    <span 
      className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white text-sm rounded-xl shadow-lg shadow-indigo-500/20 transform transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-indigo-500/30"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <span className="text-indigo-200 font-medium">{filter.field}:</span>
      <span className="font-semibold">{filter.value}</span>
      <button
        onClick={onRemove}
        className="ml-1.5 p-1 hover:bg-white/20 rounded-full transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </span>
  );
}

// Company result card with hover animation
function CompanyCard({
  company,
  onFeedback,
  index,
}: {
  company: CompanyResult;
  onFeedback: (isRelevant: boolean) => void;
  index: number;
}) {
  const [feedbackGiven, setFeedbackGiven] = useState<boolean | null>(null);
  const [isHovered, setIsHovered] = useState(false);

  const handleFeedback = (isRelevant: boolean) => {
    setFeedbackGiven(isRelevant);
    onFeedback(isRelevant);
  };

  return (
    <div 
      className={cn(
        "group bg-white border border-gray-100 rounded-2xl p-6 transition-all duration-500 ease-out",
        "hover:shadow-2xl hover:shadow-indigo-500/10 hover:border-indigo-100 hover:-translate-y-1",
        "animate-fade-in"
      )}
      style={{ animationDelay: `${index * 100}ms` }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className={cn(
            "w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300",
            isHovered 
              ? "bg-gradient-to-br from-indigo-500 to-purple-500 shadow-lg shadow-indigo-500/30" 
              : "bg-gradient-to-br from-gray-100 to-gray-50"
          )}>
            <Building2 className={cn(
              "w-6 h-6 transition-colors duration-300",
              isHovered ? "text-white" : "text-gray-400"
            )} />
          </div>
          <div>
            <h3 className="font-bold text-lg text-gray-900 group-hover:text-indigo-600 transition-colors">
              {company.name}
            </h3>
            {company.domain && (
              <a
                href={`https://${company.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-indigo-500 hover:text-indigo-700 flex items-center gap-1 transition-colors"
              >
                {company.domain}
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>

        {/* Feedback buttons */}
        <div className={cn(
          "flex items-center gap-1.5 transition-all duration-300",
          isHovered ? "opacity-100 translate-x-0" : "opacity-0 translate-x-2"
        )}>
          <button
            onClick={() => handleFeedback(true)}
            className={cn(
              'p-2.5 rounded-xl transition-all duration-200',
              feedbackGiven === true
                ? 'bg-green-100 text-green-600 shadow-md'
                : 'hover:bg-green-50 text-gray-400 hover:text-green-500'
            )}
            title="Relevant"
          >
            <ThumbsUp className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleFeedback(false)}
            className={cn(
              'p-2.5 rounded-xl transition-all duration-200',
              feedbackGiven === false
                ? 'bg-red-100 text-red-600 shadow-md'
                : 'hover:bg-red-50 text-gray-400 hover:text-red-500'
            )}
            title="Not relevant"
          >
            <ThumbsDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {company.description && (
        <p className="text-sm text-gray-600 mb-4 line-clamp-2 leading-relaxed">{company.description}</p>
      )}

      <div className="flex flex-wrap gap-4 text-sm text-gray-500">
        {company.industry && (
          <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-lg">
            <Layers className="w-4 h-4 text-indigo-400" />
            <span>{company.industry}</span>
          </div>
        )}
        {company.employee_count && (
          <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-lg">
            <Users className="w-4 h-4 text-purple-400" />
            <span>{company.employee_count}</span>
          </div>
        )}
        {company.location && (
          <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-lg">
            <MapPin className="w-4 h-4 text-blue-400" />
            <span>{company.location}</span>
          </div>
        )}
      </div>

      {company.technologies && company.technologies.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {company.technologies.slice(0, 5).map((tech) => (
            <span
              key={tech}
              className="px-2.5 py-1 bg-gradient-to-r from-indigo-50 to-purple-50 text-indigo-600 text-xs font-medium rounded-lg border border-indigo-100"
            >
              {tech}
            </span>
          ))}
          {company.technologies.length > 5 && (
            <span className="px-2.5 py-1 text-gray-400 text-xs">
              +{company.technologies.length - 5} more
            </span>
          )}
        </div>
      )}

      {/* Verification status */}
      {company.verified !== undefined && (
        <div className="mt-4 space-y-2">
          {company.verified ? (
            <div className="flex items-center gap-2 text-emerald-600 text-xs font-medium bg-emerald-50 px-3 py-1.5 rounded-lg w-fit">
              <ShieldCheck className="w-4 h-4" />
              <span>Verified match</span>
              {company.verification_confidence && (
                <span className="text-emerald-500">
                  ({Math.round(company.verification_confidence * 100)}% confidence)
                </span>
              )}
            </div>
          ) : company.verified === false ? (
            <div className="flex items-center gap-2 text-amber-600 text-xs font-medium bg-amber-50 px-3 py-1.5 rounded-lg w-fit">
              <AlertTriangle className="w-4 h-4" />
              <span>Not verified</span>
            </div>
          ) : null}
          
          {/* Verification reasons */}
          {company.verification_reasons && company.verification_reasons.length > 0 && (
            <div className="text-xs text-gray-500 pl-1">
              {company.verification_reasons.slice(0, 2).map((reason, idx) => (
                <div key={idx} className="flex items-center gap-1">
                  <Check className="w-3 h-3 text-emerald-500" />
                  {reason}
                </div>
              ))}
            </div>
          )}
          
          {/* Verification warnings */}
          {company.verification_warnings && company.verification_warnings.length > 0 && (
            <div className="text-xs text-gray-500 pl-1">
              {company.verification_warnings.slice(0, 2).map((warning, idx) => (
                <div key={idx} className="flex items-center gap-1">
                  <Info className="w-3 h-3 text-amber-500" />
                  {warning}
                </div>
              ))}
            </div>
          )}
          
          {/* AI description if detected */}
          {company.ai_description && (
            <p className="text-xs text-gray-500 italic border-l-2 border-indigo-200 pl-2">
              {company.ai_description}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// Chat message component with animation
function ChatMessageBubble({ message, isLatest }: { message: ChatMessage; isLatest: boolean }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex animate-slide-up', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('flex items-start gap-3 max-w-[85%]')}>
        {!isUser && (
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/30">
            <Bot className="w-4 h-4 text-white" />
          </div>
        )}
        <div
          className={cn(
            'rounded-2xl px-5 py-3.5 transition-all duration-300',
            isUser
              ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/20'
              : 'bg-white border border-gray-100 text-gray-900 shadow-sm'
          )}
        >
          <p className="text-sm whitespace-pre-wrap leading-relaxed">
            {isLatest && !isUser ? (
              <TypewriterText text={message.content} />
            ) : (
              message.content
            )}
          </p>
          {message.filters && message.filters.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/20 flex flex-wrap gap-2">
              {message.filters.map((filter, idx) => (
                <span
                  key={idx}
                  className={cn(
                    "px-2.5 py-1 text-xs rounded-lg font-medium",
                    isUser 
                      ? "bg-white/20 text-white" 
                      : "bg-indigo-50 text-indigo-600"
                  )}
                >
                  {filter.field}: {filter.value}
                </span>
              ))}
            </div>
          )}
        </div>
        {isUser && (
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center flex-shrink-0 shadow-lg">
            <span className="text-white text-xs font-bold">U</span>
          </div>
        )}
      </div>
    </div>
  );
}

// Feature highlight card for initial state
function FeatureCard({ icon: Icon, title, description }: { icon: any; title: string; description: string }) {
  return (
    <div className="bg-white/80 backdrop-blur-sm border border-gray-100 rounded-2xl p-5 hover:shadow-xl hover:shadow-indigo-500/5 hover:-translate-y-1 transition-all duration-300">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mb-4 shadow-lg shadow-indigo-500/30">
        <Icon className="w-5 h-5 text-white" />
      </div>
      <h3 className="font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 leading-relaxed">{description}</p>
    </div>
  );
}

// Pattern badge component for reverse engineering results
function PatternBadge({ pattern }: { pattern: ExtractedPattern }) {
  const confidenceColor = pattern.confidence >= 0.7 
    ? 'from-emerald-500 to-green-500' 
    : pattern.confidence >= 0.5 
      ? 'from-amber-500 to-yellow-500'
      : 'from-gray-400 to-gray-500';
  
  return (
    <div className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl shadow-sm">
      <span className="text-sm font-medium text-gray-700">{pattern.field}:</span>
      <span className="text-sm font-semibold text-gray-900">{pattern.value}</span>
      <span 
        className={cn(
          "px-2 py-0.5 text-xs font-bold text-white rounded-full bg-gradient-to-r",
          confidenceColor
        )}
      >
        {Math.round(pattern.confidence * 100)}%
      </span>
    </div>
  );
}

// Example company input row
function ExampleCompanyRow({
  company,
  onChange,
  onRemove,
  index,
}: {
  company: ExampleCompany;
  onChange: (updated: ExampleCompany) => void;
  onRemove: () => void;
  index: number;
}) {
  return (
    <div 
      className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-xl animate-fade-in"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center flex-shrink-0">
        <Building2 className="w-4 h-4 text-indigo-600" />
      </div>
      <div className="flex-1 grid grid-cols-4 gap-2">
        <input
          type="text"
          placeholder="Company name"
          value={company.name}
          onChange={(e) => onChange({ ...company, name: e.target.value })}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10"
        />
        <input
          type="text"
          placeholder="Domain (e.g., acme.com)"
          value={company.domain || ''}
          onChange={(e) => onChange({ ...company, domain: e.target.value })}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10"
        />
        <input
          type="text"
          placeholder="Industry"
          value={company.industry || ''}
          onChange={(e) => onChange({ ...company, industry: e.target.value })}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10"
        />
        <input
          type="text"
          placeholder="Location"
          value={company.location || ''}
          onChange={(e) => onChange({ ...company, location: e.target.value })}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10"
        />
      </div>
      <button
        onClick={onRemove}
        className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}

export function DataSearchPage() {
  const [searchMode, setSearchMode] = useState<SearchMode>('chat');
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [filters, setFilters] = useState<SearchFilter[]>([]);
  const [results, setResults] = useState<CompanyResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Reverse engineering state
  const [exampleCompanies, setExampleCompanies] = useState<ExampleCompany[]>([
    { id: '1', name: '', domain: '', industry: '', location: '' },
  ]);
  const [userContext, setUserContext] = useState('');
  const [patterns, setPatterns] = useState<ExtractedPattern[]>([]);
  const [analysisSummary, setAnalysisSummary] = useState('');
  const [searchTips, setSearchTips] = useState<string[]>([]);

  // Verification state
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationSummary, setVerificationSummary] = useState<string | null>(null);

  // Project/web search state
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId] = useState<number | null>(null);
  const [projectSearchJobId, setProjectSearchJobId] = useState<number | null>(null);
  const [projectResultsStats, setProjectResultsStats] = useState<{ total: number; targets: number } | null>(null);
  const [projectProgress, setProjectProgress] = useState<SearchProgressEvent | null>(null);
  const [projectResults, setProjectResults] = useState<SearchResultItem[]>([]);
  const [projectSpending, setProjectSpending] = useState<SpendingInfo | null>(null);
  const [isProjectSearching, setIsProjectSearching] = useState(false);
  const [maxQueries] = useState(500);
  const [targetGoal] = useState(200);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Project data cache — avoids re-fetching when switching between projects
  const projectCacheRef = useRef<Map<number, {
    results: SearchResultItem[];
    spending: SpendingInfo | null;
    autoEnrichConfig: AutoEnrichConfig | null;
    stats?: { total: number; targets: number };
    pipelineStage?: PipelineStage;
  }>>(new Map());

  // Chat-driven web search state
  const [webSearchMessages, setWebSearchMessages] = useState<ProjectChatMessage[]>([]);
  const [webSearchQuery, setWebSearchQuery] = useState('');
  const [isWebSearching, setIsWebSearching] = useState(false);
  const [webSearchProjectId, setWebSearchProjectId] = useState<number | null>(null);
  const [webSearchSuggestions, setWebSearchSuggestions] = useState<string[]>([]);
  const [lastSeenTargets, setLastSeenTargets] = useState<string[]>([]);
  const [showTargetsOnly, setShowTargetsOnly] = useState(false);
  const [expandedResultId, setExpandedResultId] = useState<number | null>(null);
  const webChatEndRef = useRef<HTMLDivElement>(null);

  // Pipeline stage and progress (for project mode)
  const [pipelineStage, setPipelineStage] = useState<PipelineStage>('idle');
  const [autoEnrichConfig, setAutoEnrichConfig] = useState<AutoEnrichConfig | null>(null);
  const [contactsProgress, setContactsProgress] = useState<string | null>(null);
  const [enrichProgress, setEnrichProgress] = useState<string | null>(null);

  const navigate = useNavigate();

  // Scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Scroll web chat messages
  useEffect(() => {
    webChatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [webSearchMessages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Auto-load chat for active project on mount
  useEffect(() => {
    if (activeSearchProjectId) {
      loadProjectChat(activeSearchProjectId);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load projects when switching to project mode (form-based)
  useEffect(() => {
    if (searchMode === 'project' && projects.length === 0) {
      contactsApi.listProjects().then(setProjects).catch(console.error);
    }
  }, [searchMode, projects.length]);

  // Load search history (projects that had searches)
  useEffect(() => {
    contactsApi.listProjectNames().then(list => {
      setSearchHistory(list as any);
    }).catch(console.error);
  }, []);

  // Persist chat messages whenever they change
  useEffect(() => {
    if (webSearchProjectId && webSearchMessages.length > 0) {
      saveChatMessages(webSearchProjectId, webSearchMessages);
    }
  }, [webSearchMessages, webSearchProjectId]);

  // Load saved chat messages when switching projects
  const loadProjectChat = useCallback((projectId: number) => {
    const saved = loadChatMessages(projectId);
    setWebSearchMessages(saved);
    setWebSearchProjectId(projectId);
    setSearchMode('project');
    // Reset pipeline running guard when switching projects
    pipelineRunningRef.current = false;
    // Check cache first for instant project switching
    const cached = projectCacheRef.current.get(projectId);
    if (cached) {
      setProjectResults(cached.results);
      setProjectSpending(cached.spending);
      setAutoEnrichConfig(cached.autoEnrichConfig);
      setProjectResultsStats(cached.stats ?? {
        total: cached.results.length,
        targets: cached.results.filter(r => r.is_target).length,
      });
      if (cached.results.length > 0 || saved.length > 0) {
        setHasSearched(true);
        // Don't set search_done — it triggers auto-extract pipeline.
        // Use 'idle' to just show the dashboard without triggering actions.
        setPipelineStage(cached.pipelineStage ?? 'idle');
      } else {
        setHasSearched(false);
      }
      return;
    }

    // Cache miss — fetch results stats from dedicated fast endpoint + results page
    const getOrCreateEntry = () =>
      projectCacheRef.current.get(projectId) || { results: [], spending: null, autoEnrichConfig: null };
    projectSearchApi.getProjectResultsStats(projectId).then(stats => {
      setProjectResultsStats({ total: stats.total, targets: stats.targets });
      const entry = getOrCreateEntry();
      entry.stats = { total: stats.total, targets: stats.targets };
      projectCacheRef.current.set(projectId, entry);
      if (stats.total > 0 || saved.length > 0) {
        setHasSearched(true);
        setPipelineStage('idle');
      } else {
        setHasSearched(false);
      }
    }).catch(() => {
      setHasSearched(saved.length > 0);
    });
    projectSearchApi.getProjectResults(projectId).then(data => {
      setProjectResults(data.items);
      const entry = getOrCreateEntry();
      entry.results = data.items;
      projectCacheRef.current.set(projectId, entry);
    }).catch(() => {});
    projectSearchApi.getProjectSpending(projectId).then(spending => {
      setProjectSpending(spending);
      const entry = getOrCreateEntry();
      entry.spending = spending;
      projectCacheRef.current.set(projectId, entry);
    }).catch(() => {});
    pipelineApi.getAutoEnrichConfig(projectId).then(config => {
      setAutoEnrichConfig(config);
      const entry = getOrCreateEntry();
      entry.autoEnrichConfig = config;
      projectCacheRef.current.set(projectId, entry);
    }).catch(() => {});
  }, [setWebSearchProjectId]);

  // Generate system messages from SSE target data
  const handleSSEProgressWithTargets = useCallback((event: SearchProgressEvent) => {
    setProjectProgress(event);

    // Live-update dashboard stats from SSE data
    if (event.results_analyzed > 0 || (event.targets_found ?? 0) > 0) {
      setProjectResultsStats(prev => ({
        total: Math.max(event.results_analyzed, prev?.total ?? 0),
        targets: Math.max(event.targets_found ?? 0, prev?.targets ?? 0),
      }));
    }

    // Post system message for new targets found
    if (event.latest_targets && event.latest_targets.length > 0) {
      const targetNames = event.latest_targets.map(t => t.name || t.domain);
      const newNames = targetNames.filter(n => !lastSeenTargets.includes(n));
      if (newNames.length > 0) {
        setLastSeenTargets(prev => [...prev, ...newNames]);
        const msg: ProjectChatMessage = {
          id: `sys-${Date.now()}`,
          role: 'system',
          content: `Found ${event.targets_found || 0} targets so far. Latest: ${newNames.join(', ')}`,
          timestamp: new Date(),
        };
        setWebSearchMessages(prev => [...prev, msg]);
      }
    }

    if (event.phase === 'completed' || event.phase === 'error' || event.phase === 'cancelled') {
      setIsProjectSearching(false);
      // Load final results and stats
      if (webSearchProjectId) {
        projectSearchApi.getProjectResults(webSearchProjectId).then(data => {
          setProjectResults(data.items);
          setProjectResultsStats({ total: data.total, targets: data.items.filter(r => r.is_target).length });
        });
        projectSearchApi.getProjectSpending(webSearchProjectId).then(setProjectSpending);
      }
      // Summary message
      const summaryMsg: ProjectChatMessage = {
        id: `sys-done-${Date.now()}`,
        role: 'assistant',
        content: event.phase === 'completed'
          ? `Search complete! Analyzed ${event.results_analyzed} companies, found ${event.targets_found || 0} targets in ${Math.round(event.elapsed_seconds)}s.`
          : event.phase === 'error'
          ? `Search failed: ${event.error_message || 'Unknown error'}`
          : 'Search was cancelled.',
        timestamp: new Date(),
      };
      setWebSearchMessages(prev => [...prev, summaryMsg]);
    }
  }, [lastSeenTargets, webSearchProjectId]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  void projects; void selectedProjectId; void maxQueries; void targetGoal; // used by chat search

  const handleCancelProjectSearch = useCallback(async () => {
    if (!projectSearchJobId) return;
    try {
      await projectSearchApi.cancelSearchJob(projectSearchJobId);
      eventSourceRef.current?.close();
      setIsProjectSearching(false);
      setPipelineStage('search_done');
      const msg: ProjectChatMessage = {
        id: `sys-cancel-${Date.now()}`,
        role: 'system',
        content: 'Search cancelled.',
        timestamp: new Date(),
      };
      setWebSearchMessages(prev => [...prev, msg]);
    } catch (error) {
      console.error('Cancel failed:', error);
    }
  }, [projectSearchJobId]);

  // Guard against duplicate pipeline auto-triggers
  const pipelineRunningRef = useRef(false);

  // Pipeline stage handlers — must be defined BEFORE the useEffects that reference them
  const handleExtractContacts = useCallback(async () => {
    if (!webSearchProjectId || pipelineStage !== 'search_done') return;
    if (pipelineRunningRef.current) return;
    pipelineRunningRef.current = true;
    setPipelineStage('contacts');
    setContactsProgress('Starting...');
    try {
      const result = await pipelineApi.extractContactsForProject(
        webSearchProjectId,
        (done, total) => setContactsProgress(`${done}/${total} companies`),
      );
      setContactsProgress(null);
      setPipelineStage('contacts_done');
      const msg: ProjectChatMessage = {
        id: `sys-contacts-${Date.now()}`,
        role: 'system',
        content: `Contacts extracted: ${result.contacts_found} contacts from ${result.processed} companies${result.errors ? ` (${result.errors} errors)` : ''}.`,
        timestamp: new Date(),
      };
      setWebSearchMessages(prev => [...prev, msg]);
    } catch (error: any) {
      console.error('Contact extraction failed:', error);
      setPipelineStage('search_done');
      setContactsProgress(null);
    } finally {
      pipelineRunningRef.current = false;
    }
  }, [webSearchProjectId, pipelineStage, autoEnrichConfig]);

  const handleEnrichApollo = useCallback(async () => {
    if (!webSearchProjectId || pipelineStage !== 'contacts_done') return;
    if (pipelineRunningRef.current) return;
    pipelineRunningRef.current = true;
    setPipelineStage('enrichment');
    setEnrichProgress('Starting...');
    try {
      const result = await pipelineApi.enrichApolloForProject(
        webSearchProjectId,
        autoEnrichConfig ?? undefined,
        (done, total) => setEnrichProgress(`${done}/${total} companies`),
      );
      setEnrichProgress(null);
      setPipelineStage('done');
      const msg: ProjectChatMessage = {
        id: `sys-enrich-${Date.now()}`,
        role: 'system',
        content: `Apollo enrichment complete: ${result.people_found} people found, ${result.credits_used} credits used${result.errors ? ` (${result.errors} errors)` : ''}.`,
        timestamp: new Date(),
      };
      setWebSearchMessages(prev => [...prev, msg]);
    } catch (error: any) {
      console.error('Apollo enrichment failed:', error);
      setPipelineStage('contacts_done');
      setEnrichProgress(null);
    } finally {
      pipelineRunningRef.current = false;
    }
  }, [webSearchProjectId, pipelineStage, autoEnrichConfig]);

  // Auto-trigger pipeline stages based on config
  useEffect(() => {
    if (pipelineStage === 'search_done' && autoEnrichConfig?.auto_extract) {
      handleExtractContacts();
    }
  }, [pipelineStage, autoEnrichConfig, handleExtractContacts]);

  useEffect(() => {
    if (pipelineStage === 'contacts_done' && autoEnrichConfig?.auto_apollo) {
      handleEnrichApollo();
    }
  }, [pipelineStage, autoEnrichConfig, handleEnrichApollo]);

  // handleExportSheet removed — using chat-driven search export instead

  // Chat-based web search handler
  const handleWebSearchChat = useCallback(async () => {
    const msg = webSearchQuery.trim();
    if (!msg || isWebSearching) return;

    const userMsg: ProjectChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date(),
    };
    setWebSearchMessages(prev => [...prev, userMsg]);
    setWebSearchQuery('');
    setIsWebSearching(true);
    setHasSearched(true);

    try {
      const context = webSearchMessages
        .filter(m => m.role !== 'system')
        .map(m => ({ role: m.role, content: m.content }));

      const response = await projectSearchApi.chatSearch(msg, {
        projectId: webSearchProjectId || undefined,
        maxQueries,
        targetGoal,
        context,
      });

      // AI reply
      const aiMsg: ProjectChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: response.reply,
        timestamp: new Date(),
      };
      setWebSearchMessages(prev => [...prev, aiMsg]);

      if (response.suggestions) {
        setWebSearchSuggestions(response.suggestions);
      }

      if (response.project_id) {
        setWebSearchProjectId(response.project_id);
      }

      // If search was started, begin SSE streaming
      if (response.action === 'search_started' && response.job_id) {
        setProjectSearchJobId(response.job_id);
        setIsProjectSearching(true);
        setProjectProgress(null);
        setLastSeenTargets([]);
        setPipelineStage('searching');

        const activePid = response.project_id || webSearchProjectId;

        if (response.preserve_results) {
          // Refine: keep existing results, re-fetch to pick up demotions
          if (activePid) {
            projectSearchApi.getProjectResults(activePid).then(data => {
              setProjectResults(data.items);
              setProjectResultsStats({ total: data.total, targets: data.items.filter(r => r.is_target).length });
            }).catch(() => {});
            projectSearchApi.getProjectSpending(activePid).then(setProjectSpending).catch(() => {});
          }
        } else {
          // Fresh search: clear results
          setProjectResults([]);
          setProjectSpending(null);
          setProjectResultsStats(null);
        }

        // Fetch auto-enrich config for the project
        if (activePid) {
          pipelineApi.getAutoEnrichConfig(activePid).then(setAutoEnrichConfig).catch(() => setAutoEnrichConfig(null));
        }

        eventSourceRef.current?.close();
        const es = projectSearchApi.streamSearchJob(
          response.job_id,
          handleSSEProgressWithTargets,
          () => {
            setIsProjectSearching(false);
            // Invalidate cache so next switch re-fetches fresh data
            if (activePid) projectCacheRef.current.delete(activePid);
          },
        );
        eventSourceRef.current = es;
      }
    } catch (error: any) {
      const errMsg: ProjectChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: error?.response?.data?.detail || 'Failed to process your request. Please try again.',
        timestamp: new Date(),
      };
      setWebSearchMessages(prev => [...prev, errMsg]);
    } finally {
      setIsWebSearching(false);
    }
  }, [webSearchQuery, isWebSearching, webSearchMessages, webSearchProjectId, maxQueries, targetGoal, handleSSEProgressWithTargets]);

  const handleWebSearchKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleWebSearchChat();
    }
  };

  const handleSearch = async () => {
    if (!query.trim() || isSearching) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuery('');
    setIsSearching(true);
    setHasSearched(true);

    try {
      // Build conversation history for context
      const conversationHistory = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await dataSearchApi.chat(query.trim(), conversationHistory);

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        filters: response.filters,
        results: response.results,
        total: response.total,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setFilters(response.filters);
      setResults(response.results);
      setTotalResults(response.total);
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          error.userMessage ||
          "I couldn't process your search. Please try again or rephrase your query.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleRemoveFilter = (index: number) => {
    const newFilters = filters.filter((_, i) => i !== index);
    setFilters(newFilters);
    // Re-run search with updated filters
    if (newFilters.length > 0) {
      setIsSearching(true);
      dataSearchApi
        .search(newFilters)
        .then((response) => {
          setResults(response.companies);
          setTotalResults(response.total);
        })
        .finally(() => setIsSearching(false));
    } else {
      setResults([]);
      setTotalResults(0);
    }
  };

  const handleFeedback = async (companyId: string, isRelevant: boolean) => {
    try {
      await dataSearchApi.feedback(companyId, 'current-search', isRelevant);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  const handleExport = async () => {
    if (filters.length === 0) return;
    try {
      const blob = await dataSearchApi.exportResults(filters, 'csv');
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'search-results.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export:', error);
    }
  };

  const handleExampleClick = (example: string) => {
    setQuery(example);
    inputRef.current?.focus();
  };

  const handleNewSearch = () => {
    setHasSearched(false);
    setMessages([]);
    setFilters([]);
    setResults([]);
    setTotalResults(0);
    setQuery('');
    setPatterns([]);
    setAnalysisSummary('');
    setSearchTips([]);
    setVerificationSummary(null);
    // Reset project search state
    setProjectSearchJobId(null);
    setProjectProgress(null);
    setProjectResults([]);
    setProjectSpending(null);
    setProjectResultsStats(null);
    setIsProjectSearching(false);
    // Reset web search state
    setWebSearchMessages([]);
    setWebSearchQuery('');
    setWebSearchProjectId(null);
    setWebSearchSuggestions([]);
    setLastSeenTargets([]);
    eventSourceRef.current?.close();
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  // Verification handler
  const handleVerifyResults = async () => {
    if (results.length === 0 || isVerifying) return;

    setIsVerifying(true);
    setVerificationSummary(null);

    try {
      // Build criteria from current filters
      const criteria: VerificationCriteria = {
        industry: filters.find(f => f.field === 'industry')?.value,
        employee_count: filters.find(f => f.field === 'employee_count')?.value,
        location: filters.find(f => f.field === 'location')?.value,
        technologies: filters.filter(f => f.field === 'technologies').map(f => f.value),
        keywords: filters.filter(f => f.field === 'keywords').map(f => f.value),
      };

      const response = await dataSearchApi.verifySearchResults(
        results,
        criteria,
        { useAi: true, verifyLimit: 10 }
      );

      setResults(response.results);
      setVerificationSummary(response.verification_summary);

      // Add verification message to chat
      const verifyMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Verification complete: ${response.verification_summary}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, verifyMessage]);

    } catch (error: any) {
      console.error('Verification failed:', error);
      setVerificationSummary('Verification failed. Please try again.');
    } finally {
      setIsVerifying(false);
    }
  };

  // Reverse engineering handlers
  const addExampleCompany = () => {
    setExampleCompanies([
      ...exampleCompanies,
      { id: Date.now().toString(), name: '', domain: '', industry: '', location: '' },
    ]);
  };

  const updateExampleCompany = (index: number, updated: ExampleCompany) => {
    const newCompanies = [...exampleCompanies];
    newCompanies[index] = updated;
    setExampleCompanies(newCompanies);
  };

  const removeExampleCompany = (index: number) => {
    if (exampleCompanies.length > 1) {
      setExampleCompanies(exampleCompanies.filter((_, i) => i !== index));
    }
  };

  const handleReverseEngineer = async () => {
    // Filter out empty companies
    const validCompanies = exampleCompanies.filter(c => c.name.trim());
    if (validCompanies.length === 0) {
      return;
    }

    setIsSearching(true);
    setHasSearched(true);

    try {
      const response = await dataSearchApi.searchLike(
        validCompanies,
        userContext || undefined,
        true
      );

      setPatterns(response.analysis.patterns);
      setAnalysisSummary(response.analysis.analysis_summary);
      setFilters(response.filters_applied);
      setResults(response.results);
      setTotalResults(response.total);
      setSearchTips(response.search_strategy?.search_tips || []);

      // Add a summary message to chat
      const summaryMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.analysis.analysis_summary,
        timestamp: new Date(),
        filters: response.filters_applied,
        results: response.results,
        total: response.total,
      };
      setMessages([summaryMessage]);
    } catch (error: any) {
      console.error('Reverse engineering failed:', error);
      setAnalysisSummary(
        error.userMessage || 'Failed to analyze companies. Please try again.'
      );
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="h-full flex relative">
      {/* Search History Sidebar */}
      {searchMode === 'project' && (
        <div className={cn(
          "h-full border-r border-gray-200 bg-gray-50 flex flex-col transition-all duration-200 flex-shrink-0",
          sidebarOpen ? "w-[240px]" : "w-0 overflow-hidden border-r-0"
        )}>
          <div className="p-3 border-b border-gray-200 flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Searches</span>
            <button
              onClick={() => { handleNewSearch(); setSearchMode('project'); }}
              className="p-1 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
              title="New search"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {searchHistory.map(p => (
              <button
                key={p.id}
                onClick={() => loadProjectChat(p.id)}
                className={cn(
                  "w-full text-left px-3 py-2.5 text-sm border-b border-gray-100 hover:bg-white transition-colors group flex items-center gap-2",
                  webSearchProjectId === p.id && "bg-white border-l-2 border-l-emerald-500"
                )}
              >
                <MessageSquare className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                <span className="truncate flex-1 text-gray-700">{p.name}</span>
                <span
                  onClick={(e) => { e.stopPropagation(); navigate(`/pipeline?project_id=${p.id}`); }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-emerald-600 rounded transition-all cursor-pointer"
                  title="View pipeline"
                  role="button"
                >
                  <Layers className="w-3.5 h-3.5" />
                </span>
              </button>
            ))}
            {searchHistory.length === 0 && (
              <div className="p-4 text-xs text-gray-400 text-center">No searches yet</div>
            )}
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex-1 h-full bg-gradient-to-b from-gray-50 to-white flex flex-col relative min-w-0">
      {searchMode !== 'project' && <AnimatedBackground />}

      {/* Mode toggle + actions bar (no sub-header label to avoid double header) */}
      <div className="bg-white/80 backdrop-blur-md border-b border-gray-100 flex items-center px-6 py-2 sticky top-0 z-40">
        {/* Mode Toggle — always visible */}
        <div className="flex items-center bg-gray-100 rounded-xl p-1">
          <button
            onClick={() => { setSearchMode('chat'); if (hasSearched && searchMode !== 'chat') handleNewSearch(); }}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all duration-200",
              searchMode === 'chat'
                ? "bg-white text-indigo-600 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <MessageSquare className="w-4 h-4" />
            Natural Language
          </button>
          <button
            onClick={() => { setSearchMode('reverse'); if (hasSearched && searchMode !== 'reverse') handleNewSearch(); }}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all duration-200",
              searchMode === 'reverse'
                ? "bg-white text-indigo-600 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <GitCompareArrows className="w-4 h-4" />
            Find Similar
          </button>
          <button
            onClick={() => { setSearchMode('project'); if (hasSearched && searchMode !== 'project') handleNewSearch(); }}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all duration-200",
              searchMode === 'project'
                ? "bg-white text-indigo-600 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <Globe className="w-4 h-4" />
            Web Search
          </button>
        </div>

        <div className="flex-1" />

        {hasSearched && (
          <button
            onClick={handleNewSearch}
            className="mr-4 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-xl flex items-center gap-2 transition-all duration-200"
          >
            <RefreshCw className="w-4 h-4" />
            New Search
          </button>
        )}
      </div>

      {/* Main content */}
      <main className="flex-1 flex flex-col relative z-10">
        {searchMode === 'project' ? (
          /* ===== PROJECT MODE: ChatGPT/Claude-like chat ===== */
          !webSearchProjectId ? (
            /* No project selected */
            <div className="flex-1 flex flex-col items-center justify-center px-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Select a Project</h2>
              <p className="text-gray-500 mb-6 text-sm">Choose a project from the sidebar to start searching</p>
              <div className="flex flex-wrap justify-center gap-3">
                {searchHistory.slice(0, 8).map(p => (
                  <button
                    key={p.id}
                    onClick={() => loadProjectChat(p.id)}
                    className="px-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl hover:border-emerald-300 hover:shadow-lg transition-all flex items-center gap-2"
                  >
                    <MessageSquare className="w-3.5 h-3.5 text-emerald-500" />
                    <span className="text-gray-700">{p.name}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Chat — full width, with compact dashboard card */
            <div className="flex-1 flex flex-col bg-white overflow-hidden">
              <div className="flex-1 flex flex-col">
                {/* Project header */}
                <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
                  <Target className="w-4 h-4 text-emerald-500" />
                  <span className="text-sm font-medium text-gray-700 truncate">
                    {searchHistory.find(p => p.id === webSearchProjectId)?.name || `Project #${webSearchProjectId}`}
                  </span>
                  <button
                    onClick={() => navigate(`/pipeline?project_id=${webSearchProjectId}`)}
                    className="ml-auto flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-100 hover:bg-emerald-200 rounded-lg transition-colors"
                  >
                    <Layers className="w-3.5 h-3.5" />
                    Pipeline
                  </button>
                </div>

                {/* Pipeline stage indicator — PipelineStageIndicator component not implemented, block commented out */}
                {/* {pipelineStage !== 'idle' && (
                  <PipelineStageIndicator
                    stage={pipelineStage}
                    contactsProgress={contactsProgress}
                    enrichProgress={enrichProgress}
                    onExtractContacts={handleExtractContacts}
                    onEnrichApollo={handleEnrichApollo}
                    autoConfig={autoEnrichConfig}
                  />
                )} */}

                {/* Chat messages */}
                <div className="flex-1 overflow-y-auto">
                  <div className="py-6 space-y-4 max-w-2xl mx-auto px-6">
                    {webSearchMessages.length === 0 && !isProjectSearching && (
                      <div className="flex flex-col items-center pt-20 text-center">
                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center mb-4">
                          <Bot className="w-7 h-7 text-emerald-600" />
                        </div>
                        <h3 className="text-lg font-semibold text-gray-700 mb-1">What are you looking for?</h3>
                        <p className="text-sm text-gray-400 max-w-sm">Describe target companies and I'll search the web to find them</p>
                      </div>
                    )}

                    {/* Compact dashboard card — shown when results exist */}
                    {(projectResultsStats && projectResultsStats.total > 0) && (
                      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold text-gray-900">
                              {projectResultsStats.total} results
                            </span>
                            <span className="text-sm text-emerald-600 font-medium">
                              {projectResultsStats.targets} targets
                            </span>
                            {projectSpending && (
                              <span
                                className="text-xs text-gray-400"
                                title={`Yandex: $${projectSpending.yandex_cost.toFixed(3)} | OpenAI: $${projectSpending.openai_cost_estimate.toFixed(3)} | Crona: ${projectSpending.crona_credits_used} credits`}
                              >
                                ${projectSpending.total_estimate.toFixed(2)}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => navigate(`/search-results?project_id=${webSearchProjectId}`)}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors border border-emerald-200"
                            >
                              <Search className="w-3.5 h-3.5" />
                              View Results
                            </button>
                            <button
                              onClick={() => navigate(`/pipeline?project_id=${webSearchProjectId}`)}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors border border-gray-200"
                            >
                              <Layers className="w-3.5 h-3.5" />
                              Pipeline
                            </button>
                            {webSearchProjectId && (
                              <button
                                onClick={async () => {
                                  try {
                                    const { sheet_url } = await projectSearchApi.exportToGoogleSheet(webSearchProjectId!);
                                    window.open(sheet_url, '_blank');
                                  } catch (e) { console.error('Export failed:', e); }
                                }}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors border border-gray-200"
                              >
                                <FileSpreadsheet className="w-3.5 h-3.5" />
                                Export
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Progress bar during active search */}
                        {isProjectSearching && projectProgress && (
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <div className="flex items-center gap-2">
                                <Loader2 className="w-3.5 h-3.5 text-emerald-500 animate-spin" />
                                <span className="text-xs text-gray-600">
                                  {projectProgress.current_phase_detail ||
                                   `${projectProgress.current}/${projectProgress.total} queries`}
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                {projectProgress.targets_found != null && (
                                  <span className="text-xs font-medium text-emerald-600">
                                    {projectProgress.targets_found} targets
                                  </span>
                                )}
                                <button
                                  onClick={handleCancelProjectSearch}
                                  className="text-xs text-red-500 hover:text-red-700 font-medium"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                            {projectProgress.total > 0 && (
                              <div className="w-full bg-gray-100 rounded-full h-1.5">
                                <div
                                  className="bg-gradient-to-r from-emerald-500 to-teal-500 h-1.5 rounded-full transition-all duration-500"
                                  style={{ width: `${Math.min(100, (projectProgress.current / projectProgress.total) * 100)}%` }}
                                />
                              </div>
                            )}
                          </div>
                        )}

                        {/* Completed state */}
                        {!isProjectSearching && projectProgress?.phase === 'completed' && (
                          <div className="flex items-center gap-2 text-xs text-emerald-600">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Search complete — {projectProgress.results_analyzed} analyzed in {Math.round(projectProgress.elapsed_seconds)}s</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Searching placeholder when no results yet */}
                    {isProjectSearching && (!projectResultsStats || projectResultsStats.total === 0) && projectProgress && (
                      <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Loader2 className="w-4 h-4 text-emerald-500 animate-spin" />
                            <span className="text-sm font-medium text-gray-900">
                              {projectProgress.current_phase_detail || `Searching... ${projectProgress.current}/${projectProgress.total} queries`}
                            </span>
                          </div>
                          <button
                            onClick={handleCancelProjectSearch}
                            className="text-xs text-red-500 hover:text-red-700 font-medium"
                          >
                            Cancel
                          </button>
                        </div>
                        {projectProgress.total > 0 && (
                          <div className="w-full bg-emerald-100 rounded-full h-1.5">
                            <div
                              className="bg-gradient-to-r from-emerald-500 to-teal-500 h-1.5 rounded-full transition-all duration-500"
                              style={{ width: `${Math.min(100, (projectProgress.current / projectProgress.total) * 100)}%` }}
                            />
                          </div>
                        )}
                      </div>
                    )}

                    {webSearchMessages.map((msg) => (
                      <div key={msg.id} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                        <div className={cn('flex items-start gap-2 max-w-[90%]')}>
                          {msg.role !== 'user' && (
                            <div className={cn(
                              "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0",
                              msg.role === 'system'
                                ? "bg-emerald-100"
                                : "bg-gradient-to-br from-emerald-500 to-teal-600 shadow-md"
                            )}>
                              {msg.role === 'system' ? (
                                <Target className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Bot className="w-3.5 h-3.5 text-white" />
                              )}
                            </div>
                          )}
                          <div className={cn(
                            'rounded-2xl px-4 py-2.5 text-sm',
                            msg.role === 'user'
                              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md'
                              : msg.role === 'system'
                              ? 'bg-emerald-50 border border-emerald-100 text-emerald-800'
                              : 'bg-white border border-gray-100 text-gray-900 shadow-sm'
                          )}>
                            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                          </div>
                          {msg.role === 'user' && (
                            <div className="w-7 h-7 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0">
                              <span className="text-white text-xs font-bold">U</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}

                    {isWebSearching && (
                      <div className="flex justify-start">
                        <div className="flex items-start gap-2">
                          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md">
                            <Bot className="w-3.5 h-3.5 text-white" />
                          </div>
                          <div className="bg-white border border-gray-100 rounded-2xl px-4 py-2.5 shadow-sm">
                            <TypingIndicator />
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={webChatEndRef} />
                  </div>
                </div>

                {/* Suggestion chips */}
                {webSearchSuggestions.length > 0 && !isWebSearching && (
                  <div className="px-4 py-2 border-t border-gray-100 flex flex-wrap gap-2">
                    {webSearchSuggestions.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => setWebSearchQuery(s)}
                        className="px-3 py-1.5 text-xs bg-emerald-50 text-emerald-700 rounded-lg hover:bg-emerald-100 transition-colors border border-emerald-100"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}

                {/* Chat input — always at bottom */}
                <div className="p-4 border-t border-gray-100 bg-white pb-8">
                  <div className="relative max-w-2xl mx-auto">
                    <input
                      type="text"
                      value={webSearchQuery}
                      onChange={(e) => setWebSearchQuery(e.target.value)}
                      onKeyDown={handleWebSearchKeyDown}
                      placeholder={isProjectSearching ? "Give feedback to refine results..." : webSearchMessages.length > 0 ? "Ask about results or refine search..." : "Describe companies to find..."}
                      className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10 text-sm"
                    />
                    <button
                      onClick={handleWebSearchChat}
                      disabled={!webSearchQuery.trim() || isWebSearching}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

            </div>
          )
        ) : !hasSearched ? (
          // Initial state for chat/reverse modes
          <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 max-w-7xl mx-auto w-full">
            {searchMode === 'chat' ? (
              // Chat mode - natural language search
              <>
                <div className="text-center mb-10 animate-fade-in">
                  <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-indigo-50 text-indigo-600 text-sm font-medium rounded-full mb-6">
                    <Sparkles className="w-4 h-4" />
                    AI-Powered Search
                  </div>
                  <h1 className="text-5xl font-bold text-gray-900 mb-4 tracking-tight">
                    Find Your{' '}
                    <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                      Ideal Customers
                    </span>
                  </h1>
                  <p className="text-xl text-gray-500 max-w-xl mx-auto leading-relaxed">
                    Describe your target companies in plain English and let AI find the
                    perfect matches instantly.
                  </p>
                </div>

                {/* Search input */}
                <div className="w-full max-w-2xl mb-10 animate-slide-up">
                  <div className="relative group">
                    <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-2xl opacity-0 group-focus-within:opacity-100 blur-xl transition-opacity duration-500" />
                    <div className="relative bg-white rounded-2xl shadow-2xl shadow-indigo-500/10 border border-gray-200 overflow-hidden">
                      <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="e.g., SaaS companies in Germany with 50-200 employees..."
                        className="w-full px-6 py-5 pr-16 text-lg bg-transparent focus:outline-none placeholder-gray-400"
                      />
                      <button
                        onClick={handleSearch}
                        disabled={!query.trim() || isSearching}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl hover:shadow-lg hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 hover:scale-105"
                      >
                        {isSearching ? (
                          <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                          <Send className="w-5 h-5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Example queries */}
                <div className="text-center mb-12 animate-fade-in" style={{ animationDelay: '200ms' }}>
                  <p className="text-sm text-gray-500 mb-4 font-medium">Try these examples:</p>
                  <div className="flex flex-wrap justify-center gap-3">
                    {EXAMPLE_QUERIES.map(({ text, icon: Icon }) => (
                      <button
                        key={text}
                        onClick={() => handleExampleClick(text)}
                        className="group px-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl hover:border-indigo-300 hover:shadow-lg hover:shadow-indigo-500/5 transition-all duration-300 flex items-center gap-2"
                      >
                        <Icon className="w-4 h-4 text-gray-400 group-hover:text-indigo-500 transition-colors" />
                        <span className="text-gray-600 group-hover:text-gray-900">{text}</span>
                        <ArrowRight className="w-3 h-3 text-gray-300 group-hover:text-indigo-500 group-hover:translate-x-0.5 transition-all" />
                      </button>
                    ))}
                  </div>
                </div>

                {/* Feature cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5 w-full max-w-4xl animate-fade-in" style={{ animationDelay: '400ms' }}>
                  <FeatureCard
                    icon={Target}
                    title="Natural Language"
                    description="Describe your ideal customer profile in plain English - no complex filters needed."
                  />
                  <FeatureCard
                    icon={Zap}
                    title="Instant Results"
                    description="AI understands your query and finds matching companies in seconds."
                  />
                  <FeatureCard
                    icon={BarChart3}
                    title="Verified Data"
                    description="Access verified company data with accurate firmographics and contact info."
                  />
                </div>
              </>
            ) : searchMode === 'reverse' ? (
              // Reverse engineering mode - find similar companies
              <>
                <div className="text-center mb-10 animate-fade-in">
                  <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-purple-50 text-purple-600 text-sm font-medium rounded-full mb-6">
                    <GitCompareArrows className="w-4 h-4" />
                    Reverse Engineering Search
                  </div>
                  <h1 className="text-5xl font-bold text-gray-900 mb-4 tracking-tight">
                    Find{' '}
                    <span className="bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text text-transparent">
                      Similar Companies
                    </span>
                  </h1>
                  <p className="text-xl text-gray-500 max-w-2xl mx-auto leading-relaxed">
                    Add companies you already know and like. AI will analyze what they have in common
                    and find more companies just like them.
                  </p>
                </div>

                {/* Example companies input */}
                <div className="w-full max-w-4xl mb-8 animate-slide-up">
                  <div className="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl p-6 shadow-xl shadow-purple-500/5">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <Building2 className="w-5 h-5 text-purple-500" />
                      Example Companies
                    </h3>
                    
                    <div className="space-y-3 mb-4">
                      {exampleCompanies.map((company, index) => (
                        <ExampleCompanyRow
                          key={company.id}
                          company={company}
                          onChange={(updated) => updateExampleCompany(index, updated)}
                          onRemove={() => removeExampleCompany(index)}
                          index={index}
                        />
                      ))}
                    </div>

                    <button
                      onClick={addExampleCompany}
                      className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 hover:text-purple-600 hover:border-purple-300 transition-colors flex items-center justify-center gap-2"
                    >
                      <Plus className="w-4 h-4" />
                      Add Another Company
                    </button>

                    {/* Optional context */}
                    <div className="mt-6">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        What are you looking for? (optional)
                      </label>
                      <input
                        type="text"
                        value={userContext}
                        onChange={(e) => setUserContext(e.target.value)}
                        placeholder="e.g., Companies to sell our marketing automation tool to..."
                        className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-500/10"
                      />
                    </div>

                    {/* Search button */}
                    <button
                      onClick={handleReverseEngineer}
                      disabled={!exampleCompanies.some(c => c.name.trim()) || isSearching}
                      className="mt-6 w-full py-4 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl font-semibold hover:shadow-lg hover:shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 flex items-center justify-center gap-2"
                    >
                      {isSearching ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <Search className="w-5 h-5" />
                          Find Similar Companies
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Feature cards for reverse mode */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5 w-full max-w-4xl animate-fade-in" style={{ animationDelay: '200ms' }}>
                  <FeatureCard
                    icon={GitCompareArrows}
                    title="Pattern Detection"
                    description="AI analyzes your example companies to find what they have in common."
                  />
                  <FeatureCard
                    icon={Lightbulb}
                    title="Smart Filters"
                    description="Automatically generates search filters based on detected patterns."
                  />
                  <FeatureCard
                    icon={Target}
                    title="Similar Matches"
                    description="Finds companies with the same characteristics as your examples."
                  />
                </div>
              </>
            ) : searchMode === 'project' ? (
              // Chat-driven web search mode
              <>
                <div className="text-center mb-10 animate-fade-in">
                  <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-emerald-50 text-emerald-600 text-sm font-medium rounded-full mb-6">
                    <Globe className="w-4 h-4" />
                    AI Web Search Pipeline
                  </div>
                  <h1 className="text-5xl font-bold text-gray-900 mb-4 tracking-tight">
                    Search the{' '}
                    <span className="bg-gradient-to-r from-emerald-600 to-teal-600 bg-clip-text text-transparent">
                      Entire Web
                    </span>
                  </h1>
                  <p className="text-xl text-gray-500 max-w-2xl mx-auto leading-relaxed">
                    Describe your target companies. AI will generate search queries, crawl the web, and analyze every website to find matches.
                  </p>
                </div>

                {/* Chat input for web search */}
                <div className="w-full max-w-2xl mb-10 animate-slide-up">
                  <div className="relative group">
                    <div className="absolute inset-0 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-2xl opacity-0 group-focus-within:opacity-100 blur-xl transition-opacity duration-500" />
                    <div className="relative bg-white rounded-2xl shadow-2xl shadow-emerald-500/10 border border-gray-200 overflow-hidden">
                      <input
                        type="text"
                        value={webSearchQuery}
                        onChange={(e) => setWebSearchQuery(e.target.value)}
                        onKeyDown={handleWebSearchKeyDown}
                        placeholder="Describe the companies you're looking for..."
                        className="w-full px-6 py-5 pr-16 text-lg bg-transparent focus:outline-none placeholder-gray-400"
                      />
                      <button
                        onClick={handleWebSearchChat}
                        disabled={!webSearchQuery.trim() || isWebSearching}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:shadow-lg hover:shadow-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 hover:scale-105"
                      >
                        {isWebSearching ? (
                          <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                          <Send className="w-5 h-5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Example web searches */}
                <div className="text-center mb-12 animate-fade-in" style={{ animationDelay: '200ms' }}>
                  <p className="text-sm text-gray-500 mb-4 font-medium">Try these examples:</p>
                  <div className="flex flex-wrap justify-center gap-3">
                    {WEB_SEARCH_EXAMPLES.map(({ text, icon: Icon }) => (
                      <button
                        key={text}
                        onClick={() => setWebSearchQuery(text)}
                        className="group px-4 py-2.5 text-sm bg-white border border-gray-200 rounded-xl hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-500/5 transition-all duration-300 flex items-center gap-2"
                      >
                        <Icon className="w-4 h-4 text-gray-400 group-hover:text-emerald-500 transition-colors" />
                        <span className="text-gray-600 group-hover:text-gray-900">{text}</span>
                        <ArrowRight className="w-3 h-3 text-gray-300 group-hover:text-emerald-500 group-hover:translate-x-0.5 transition-all" />
                      </button>
                    ))}
                  </div>
                </div>

                {/* Feature cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-5 w-full max-w-4xl animate-fade-in" style={{ animationDelay: '400ms' }}>
                  <FeatureCard
                    icon={MessageSquare}
                    title="Conversational"
                    description="Describe your ideal targets in plain language. Give feedback mid-search to refine results."
                  />
                  <FeatureCard
                    icon={Globe}
                    title="Web Crawling"
                    description="AI generates search queries, crawls Yandex results, and scrapes every company website."
                  />
                  <FeatureCard
                    icon={ShieldCheck}
                    title="GPT Analysis"
                    description="Each website is analyzed by GPT to determine if it matches your target profile."
                  />
                </div>
              </>
            ) : null}
          </div>
        ) : (searchMode as SearchMode) === 'project' && hasSearched ? (
          // Chat-driven web search results view — split layout
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Chat panel */}
            <div className="w-[420px] border-r border-gray-100 bg-gradient-to-b from-white to-gray-50 flex flex-col">
              {/* Progress bar at top */}
              {projectProgress && (
                <div className="px-4 py-3 bg-gradient-to-r from-emerald-50 to-teal-50 border-b border-emerald-100">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {projectProgress.phase === 'completed' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      ) : projectProgress.phase === 'error' ? (
                        <XCircle className="w-4 h-4 text-red-500" />
                      ) : (
                        <Loader2 className="w-4 h-4 text-emerald-500 animate-spin" />
                      )}
                      <span className="text-sm font-medium text-gray-900">
                        {projectProgress.current_phase_detail ||
                         (projectProgress.phase === 'completed' ? 'Complete' :
                          projectProgress.phase === 'error' ? 'Error' :
                          `${projectProgress.current}/${projectProgress.total} queries`)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {projectProgress.targets_found != null && (
                        <span className="text-xs font-medium text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full">
                          {projectProgress.targets_found} targets
                        </span>
                      )}
                      {isProjectSearching && (
                        <button
                          onClick={handleCancelProjectSearch}
                          className="p-1 text-red-500 hover:bg-red-50 rounded transition-colors"
                          title="Cancel search"
                        >
                          <StopCircle className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  {projectProgress.total > 0 && (
                    <div className="w-full bg-emerald-100 rounded-full h-1.5">
                      <div
                        className="bg-gradient-to-r from-emerald-500 to-teal-500 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, (projectProgress.current / projectProgress.total) * 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Chat messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {webSearchMessages.map((msg) => (
                  <div key={msg.id} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                    <div className={cn('flex items-start gap-2 max-w-[90%]')}>
                      {msg.role !== 'user' && (
                        <div className={cn(
                          "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0",
                          msg.role === 'system'
                            ? "bg-emerald-100"
                            : "bg-gradient-to-br from-emerald-500 to-teal-600 shadow-md"
                        )}>
                          {msg.role === 'system' ? (
                            <Target className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Bot className="w-3.5 h-3.5 text-white" />
                          )}
                        </div>
                      )}
                      <div className={cn(
                        'rounded-2xl px-4 py-2.5 text-sm',
                        msg.role === 'user'
                          ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md'
                          : msg.role === 'system'
                          ? 'bg-emerald-50 border border-emerald-100 text-emerald-800'
                          : 'bg-white border border-gray-100 text-gray-900 shadow-sm'
                      )}>
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      </div>
                      {msg.role === 'user' && (
                        <div className="w-7 h-7 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0">
                          <span className="text-white text-xs font-bold">U</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isWebSearching && (
                  <div className="flex justify-start">
                    <div className="flex items-start gap-2">
                      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md">
                        <Bot className="w-3.5 h-3.5 text-white" />
                      </div>
                      <div className="bg-white border border-gray-100 rounded-2xl px-4 py-2.5 shadow-sm">
                        <TypingIndicator />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={webChatEndRef} />
              </div>

              {/* Suggestion chips */}
              {webSearchSuggestions.length > 0 && !isWebSearching && (
                <div className="px-4 py-2 border-t border-gray-100 flex flex-wrap gap-2">
                  {webSearchSuggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => setWebSearchQuery(s)}
                      className="px-3 py-1.5 text-xs bg-emerald-50 text-emerald-700 rounded-lg hover:bg-emerald-100 transition-colors border border-emerald-100"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {/* Chat input */}
              <div className="p-4 border-t border-gray-100 bg-white">
                <div className="relative">
                  <input
                    type="text"
                    value={webSearchQuery}
                    onChange={(e) => setWebSearchQuery(e.target.value)}
                    onKeyDown={handleWebSearchKeyDown}
                    placeholder={isProjectSearching ? "Give feedback to refine results..." : "Describe companies to find..."}
                    className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/10 text-sm"
                  />
                  <button
                    onClick={handleWebSearchChat}
                    disabled={!webSearchQuery.trim() || isWebSearching}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Right: Results panel */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Controls bar */}
              <div className="px-6 py-3 bg-white border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium text-gray-700">
                    {projectResults.length} results
                    {projectProgress?.targets_found ? ` (${projectProgress.targets_found} targets)` : ''}
                  </span>
                  <button
                    onClick={() => setShowTargetsOnly(!showTargetsOnly)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors",
                      showTargetsOnly
                        ? "bg-emerald-100 text-emerald-700 border border-emerald-200"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    )}
                  >
                    {showTargetsOnly ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                    {showTargetsOnly ? 'Targets Only' : 'Show All'}
                  </button>
                </div>
                <div className="flex items-center gap-3">
                  {projectSpending && (
                    <span className="text-xs text-gray-400">
                      Cost: ${projectSpending.total_estimate.toFixed(4)}
                    </span>
                  )}
                  {webSearchProjectId && (
                    <button
                      onClick={async () => {
                        try {
                          const { sheet_url } = await projectSearchApi.exportToGoogleSheet(webSearchProjectId);
                          window.open(sheet_url, '_blank');
                        } catch (e) { console.error('Export failed:', e); }
                      }}
                      disabled={projectResults.length === 0}
                      className="flex items-center gap-2 px-4 py-2 text-sm bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
                    >
                      <FileSpreadsheet className="w-4 h-4" />
                      Export
                    </button>
                  )}
                </div>
              </div>

              {/* Results list */}
              <div className="flex-1 overflow-y-auto p-6">
                {projectResults.length > 0 ? (
                  <div className="space-y-3">
                    {(showTargetsOnly ? projectResults.filter(r => r.is_target) : projectResults).map((result) => (
                      <div
                        key={result.id}
                        className={cn(
                          "bg-white border rounded-xl p-4 transition-all duration-200 hover:shadow-md",
                          result.is_target ? "border-emerald-200" : "border-gray-200"
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "w-10 h-10 rounded-lg flex items-center justify-center",
                              result.is_target ? "bg-emerald-100" : "bg-gray-100"
                            )}>
                              <Building2 className={cn(
                                "w-5 h-5",
                                result.is_target ? "text-emerald-600" : "text-gray-400"
                              )} />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-gray-900">
                                  {result.company_info?.name || result.domain}
                                </span>
                                {result.is_target ? (
                                  <span className="px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700 rounded-full">
                                    Target
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 rounded-full">
                                    Not Target
                                  </span>
                                )}
                                {result.confidence != null && (
                                  <span className="text-xs text-gray-500">
                                    {Math.round(result.confidence * 100)}%
                                  </span>
                                )}
                              </div>
                              <a
                                href={result.url || `https://${result.domain}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-indigo-500 hover:text-indigo-700 flex items-center gap-1"
                              >
                                {result.domain}
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            </div>
                          </div>
                          <button
                            onClick={() => setExpandedResultId(expandedResultId === result.id ? null : result.id)}
                            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                          >
                            <ChevronDown className={cn(
                              "w-4 h-4 transition-transform",
                              expandedResultId === result.id && "rotate-180"
                            )} />
                          </button>
                        </div>

                        {result.company_info?.description && (
                          <p className="text-sm text-gray-600 mt-2 ml-13">{result.company_info.description}</p>
                        )}

                        <div className="flex flex-wrap gap-2 mt-2 ml-13">
                          {result.company_info?.industry && (
                            <span className="px-2 py-0.5 text-xs bg-indigo-50 text-indigo-600 rounded-lg">{result.company_info.industry}</span>
                          )}
                          {result.company_info?.location && (
                            <span className="px-2 py-0.5 text-xs bg-blue-50 text-blue-600 rounded-lg">{result.company_info.location}</span>
                          )}
                          {result.company_info?.services?.slice(0, 3).map((svc, idx) => (
                            <span key={idx} className="px-2 py-0.5 text-xs bg-purple-50 text-purple-600 rounded-lg">{svc}</span>
                          ))}
                        </div>

                        {expandedResultId === result.id && (
                          <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                            {result.reasoning && (
                              <div>
                                <span className="text-xs font-medium text-gray-500">GPT Reasoning:</span>
                                <p className="text-sm text-gray-700 mt-1">{result.reasoning}</p>
                              </div>
                            )}
                            {result.company_info?.services && result.company_info.services.length > 0 && (
                              <div>
                                <span className="text-xs font-medium text-gray-500">Services:</span>
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {result.company_info.services.map((svc, idx) => (
                                    <span key={idx} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">{svc}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                            <div className="text-xs text-gray-400">
                              Scraped: {result.scraped_at || 'N/A'} | Analyzed: {result.analyzed_at || 'N/A'}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : isProjectSearching ? (
                  <div className="flex flex-col items-center justify-center h-full text-center">
                    <Loader2 className="w-12 h-12 text-emerald-400 animate-spin mb-4" />
                    <h3 className="text-lg font-semibold text-gray-700 mb-2">
                      Searching the web...
                    </h3>
                    <p className="text-gray-500 text-sm max-w-sm">
                      Results will appear here as websites are analyzed. You can give feedback in the chat.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center">
                    <Globe className="w-12 h-12 text-gray-300 mb-4" />
                    <h3 className="text-lg font-semibold text-gray-700 mb-2">
                      No results yet
                    </h3>
                    <p className="text-gray-500 text-sm max-w-sm">
                      Describe your target companies in the chat to start searching.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          // Search results state - chat + results
          <div className="flex-1 flex flex-col">
            {/* Patterns section (for reverse engineering) */}
            {patterns.length > 0 && (
              <div className="px-6 py-4 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-100">
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-3">
                      <Lightbulb className="w-5 h-5 text-purple-500" />
                      <span className="font-semibold text-gray-900">Detected Patterns</span>
                    </div>
                    <div className="flex flex-wrap gap-2 mb-3">
                      {patterns.slice(0, 6).map((pattern, idx) => (
                        <PatternBadge key={idx} pattern={pattern} />
                      ))}
                    </div>
                    {analysisSummary && (
                      <p className="text-sm text-gray-600">{analysisSummary}</p>
                    )}
                    {searchTips.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {searchTips.map((tip, idx) => (
                          <span key={idx} className="text-xs text-purple-600 bg-purple-100 px-2 py-1 rounded-lg">
                            {tip}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Applied filters */}
            {filters.length > 0 && (
              <div className="px-6 py-4 bg-white/80 backdrop-blur-sm border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="flex items-center gap-2 text-gray-500 mr-2">
                      <Filter className="w-4 h-4" />
                      <span className="text-sm font-medium">Filters:</span>
                    </div>
                    {filters.map((filter, idx) => (
                      <FilterChip
                        key={idx}
                        filter={filter}
                        onRemove={() => handleRemoveFilter(idx)}
                        index={idx}
                      />
                    ))}
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-500 font-medium">
                      {totalResults.toLocaleString()} results
                      {verificationSummary && (
                        <span className="ml-2 text-emerald-600">• {verificationSummary}</span>
                      )}
                    </span>
                    <button
                      onClick={handleVerifyResults}
                      disabled={isVerifying || results.length === 0}
                      className={cn(
                        "flex items-center gap-2 px-4 py-2 text-sm rounded-xl font-medium transition-all duration-300",
                        isVerifying
                          ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                          : "bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-200"
                      )}
                      title="Verify companies by scraping their websites and checking if they match criteria"
                    >
                      {isVerifying ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Verifying...
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="w-4 h-4" />
                          Verify
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleExport}
                      className="flex items-center gap-2 px-4 py-2 text-sm bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl hover:shadow-lg hover:shadow-indigo-500/30 transition-all duration-300 font-medium"
                    >
                      <Download className="w-4 h-4" />
                      Export
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex-1 flex overflow-hidden">
              {/* Chat sidebar */}
              <div className="w-[420px] border-r border-gray-100 bg-gradient-to-b from-white to-gray-50 flex flex-col">
                <div className="flex-1 overflow-y-auto p-5 space-y-5">
                  {messages.map((message, index) => (
                    <ChatMessageBubble 
                      key={message.id} 
                      message={message} 
                      isLatest={index === messages.length - 1}
                    />
                  ))}
                  {isSearching && (
                    <div className="flex justify-start animate-fade-in">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                          <Bot className="w-4 h-4 text-white" />
                        </div>
                        <div className="bg-white border border-gray-100 rounded-2xl px-5 py-3.5 shadow-sm">
                          <TypingIndicator />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Chat input */}
                <div className="p-4 border-t border-gray-100 bg-white">
                  <div className="relative">
                    <input
                      ref={inputRef}
                      type="text"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Refine your search..."
                      className="w-full px-4 py-3.5 pr-14 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 transition-all duration-200"
                    />
                    <button
                      onClick={handleSearch}
                      disabled={!query.trim() || isSearching}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:shadow-lg hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Results grid */}
              <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-br from-gray-50 to-white">
                {results.length > 0 ? (
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                    {results.map((company, index) => (
                      <CompanyCard
                        key={company.id}
                        company={company}
                        onFeedback={(isRelevant) =>
                          handleFeedback(company.id, isRelevant)
                        }
                        index={index}
                      />
                    ))}
                  </div>
                ) : (
                  !isSearching && (
                    <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in">
                      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-50 flex items-center justify-center mb-6">
                        <Globe className="w-10 h-10 text-gray-300" />
                      </div>
                      <h3 className="text-xl font-semibold text-gray-700 mb-2">
                        No results yet
                      </h3>
                      <p className="text-gray-500 max-w-sm">
                        Describe your ideal customers in the chat to start discovering companies
                      </p>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
    </div>
  );
}

export default DataSearchPage;
