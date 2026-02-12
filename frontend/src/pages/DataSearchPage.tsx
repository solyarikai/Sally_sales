import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react';
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
  ChevronDown,
  FileSpreadsheet,
  StopCircle,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';
import type { SearchFilter, CompanyResult, ChatMessage, ExtractedPattern, VerificationCriteria, SearchProgressEvent, SearchResultItem, SpendingInfo } from '../api/dataSearch';
import { dataSearchApi, projectSearchApi } from '../api/dataSearch';
import { contactsApi, type Project } from '../api/contacts';
import { pipelineApi, type AutoEnrichConfig } from '../api/pipeline';
import { useAppStore } from '../store/appStore';

// Search modes
type SearchMode = 'chat' | 'reverse' | 'project';

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
  const isSystem = message.role === 'system';

  return (
    <div className={cn('flex animate-slide-up', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('flex items-start gap-3 max-w-[85%]')}>
        {!isUser && (
          <div className={cn(
            "w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0",
            isSystem
              ? "bg-amber-100"
              : "bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30"
          )}>
            {isSystem ? (
              <Search className="w-4 h-4 text-amber-600" />
            ) : (
              <Bot className="w-4 h-4 text-white" />
            )}
          </div>
        )}
        <div
          className={cn(
            'rounded-2xl px-5 py-3.5 transition-all duration-300',
            isUser
              ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/20'
              : isSystem
              ? 'bg-amber-50 border border-amber-200 text-amber-800'
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

// Pipeline stage type for the unified Search → Contacts → Enrichment flow
type PipelineStage = 'idle' | 'searching' | 'search_done' | 'contacts' | 'contacts_done' | 'enrichment' | 'done';

// Pipeline stage indicator component
function PipelineStageIndicator({
  stage,
  contactsProgress,
  enrichProgress,
  onExtractContacts,
  onEnrichApollo,
  autoConfig,
}: {
  stage: PipelineStage;
  contactsProgress: string | null;
  enrichProgress: string | null;
  onExtractContacts: () => void;
  onEnrichApollo: () => void;
  autoConfig: AutoEnrichConfig | null;
}) {
  const steps: { key: string; label: string; num: number }[] = [
    { key: 'search', label: 'Search', num: 1 },
    { key: 'contacts', label: 'Contacts', num: 2 },
    { key: 'enrichment', label: 'Enrichment', num: 3 },
  ];

  const getStepStatus = (step: string): 'pending' | 'active' | 'completed' | 'actionable' | 'queued' => {
    if (step === 'search') {
      if (stage === 'searching') return 'active';
      if (stage !== 'idle') return 'completed';
      return 'pending';
    }
    if (step === 'contacts') {
      if (stage === 'contacts') return 'active';
      if (['contacts_done', 'enrichment', 'done'].includes(stage)) return 'completed';
      if (stage === 'search_done') {
        return autoConfig?.auto_extract ? 'queued' : 'actionable';
      }
      return 'pending';
    }
    if (step === 'enrichment') {
      if (stage === 'enrichment') return 'active';
      if (stage === 'done') return 'completed';
      if (stage === 'contacts_done') {
        return autoConfig?.auto_apollo ? 'queued' : 'actionable';
      }
      if (stage === 'search_done' && autoConfig?.auto_extract && autoConfig?.auto_apollo) return 'queued';
      return 'pending';
    }
    return 'pending';
  };

  return (
    <div className="px-4 py-3 bg-white/80 backdrop-blur-sm border-b border-gray-100">
      <div className="flex items-center justify-center gap-0">
        {steps.map((step, idx) => {
          const status = getStepStatus(step.key);
          return (
            <div key={step.key} className="flex items-center">
              {/* Connector line */}
              {idx > 0 && (
                <div className={cn(
                  "w-16 h-0.5 mx-1",
                  status === 'completed' || status === 'active' ? "bg-emerald-400" : "bg-gray-200"
                )} />
              )}

              {/* Step */}
              <div className="flex items-center gap-2">
                {/* Circle */}
                <div className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300",
                  status === 'completed' && "bg-emerald-500 text-white",
                  status === 'active' && "bg-emerald-500 text-white animate-pulse",
                  status === 'actionable' && "border-2 border-emerald-500 text-emerald-600 bg-emerald-50",
                  status === 'queued' && "border-2 border-amber-400 text-amber-600 bg-amber-50",
                  status === 'pending' && "border-2 border-gray-300 text-gray-400 bg-white",
                )}>
                  {status === 'completed' ? (
                    <Check className="w-4 h-4" />
                  ) : status === 'active' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    step.num
                  )}
                </div>

                {/* Label + action */}
                <div className="flex flex-col">
                  <span className={cn(
                    "text-sm font-medium",
                    status === 'completed' && "text-emerald-700",
                    status === 'active' && "text-emerald-700",
                    status === 'actionable' && "text-emerald-600",
                    status === 'queued' && "text-amber-600",
                    status === 'pending' && "text-gray-400",
                  )}>
                    {step.label}
                  </span>

                  {/* Progress text for active stages */}
                  {status === 'active' && step.key === 'contacts' && contactsProgress && (
                    <span className="text-xs text-emerald-500">{contactsProgress}</span>
                  )}
                  {status === 'active' && step.key === 'enrichment' && enrichProgress && (
                    <span className="text-xs text-emerald-500">{enrichProgress}</span>
                  )}

                  {/* Queued label */}
                  {status === 'queued' && (
                    <span className="text-xs text-amber-500">Queued</span>
                  )}

                  {/* Action button for actionable steps */}
                  {status === 'actionable' && step.key === 'contacts' && (
                    <button
                      onClick={onExtractContacts}
                      className="text-xs text-emerald-600 hover:text-emerald-800 font-medium flex items-center gap-1 mt-0.5"
                    >
                      <Users className="w-3 h-3" />
                      Extract Contacts
                    </button>
                  )}
                  {status === 'actionable' && step.key === 'enrichment' && (
                    <button
                      onClick={onEnrichApollo}
                      className="text-xs text-emerald-600 hover:text-emerald-800 font-medium flex items-center gap-1 mt-0.5"
                    >
                      <Zap className="w-3 h-3" />
                      Enrich Apollo
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Persist chat messages in localStorage keyed by project ID
function saveChatMessages(projectId: number, messages: ProjectChatMessage[]) {
  try {
    localStorage.setItem(`chat-${projectId}`, JSON.stringify(messages));
  } catch { /* quota exceeded - silently ignore */ }
}
function loadChatMessages(projectId: number): ProjectChatMessage[] {
  try {
    const raw = localStorage.getItem(`chat-${projectId}`);
    if (!raw) return [];
    return JSON.parse(raw).map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) }));
  } catch { return []; }
}

export function DataSearchPage() {
  const navigate = useNavigate();
  const { activeSearchProjectId, setActiveSearchProjectId } = useAppStore();
  const [searchMode, setSearchMode] = useState<SearchMode>('project');
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchHistory, setSearchHistory] = useState<{ id: number; name: string }[]>([]);
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
  const [projectProgress, setProjectProgress] = useState<SearchProgressEvent | null>(null);
  const [projectResults, setProjectResults] = useState<SearchResultItem[]>([]);
  const [projectSpending, setProjectSpending] = useState<SpendingInfo | null>(null);
  const [isProjectSearching, setIsProjectSearching] = useState(false);
  const [showTargetsOnly, setShowTargetsOnly] = useState(false);
  const [maxQueries] = useState(500);
  const [targetGoal] = useState(200);
  const [expandedResultId, setExpandedResultId] = useState<number | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Chat-driven web search state
  const [webSearchMessages, setWebSearchMessages] = useState<ProjectChatMessage[]>([]);
  const [webSearchQuery, setWebSearchQuery] = useState('');
  const [isWebSearching, setIsWebSearching] = useState(false);
  const [webSearchProjectId, setWebSearchProjectIdState] = useState<number | null>(activeSearchProjectId);
  const setWebSearchProjectId = useCallback((id: number | null) => {
    setWebSearchProjectIdState(id);
    setActiveSearchProjectId(id);
  }, [setActiveSearchProjectId]);
  const [webSearchSuggestions, setWebSearchSuggestions] = useState<string[]>([]);
  const [lastSeenTargets, setLastSeenTargets] = useState<string[]>([]);
  const webChatEndRef = useRef<HTMLDivElement>(null);

  // Pipeline stage state
  const [pipelineStage, setPipelineStage] = useState<PipelineStage>('idle');
  const [contactsProgress, setContactsProgress] = useState<string | null>(null);
  const [enrichProgress, setEnrichProgress] = useState<string | null>(null);
  const [autoEnrichConfig, setAutoEnrichConfig] = useState<AutoEnrichConfig | null>(null);

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

  // Load projects when switching to project mode (form-based)
  useEffect(() => {
    if (searchMode === 'project' && projects.length === 0) {
      contactsApi.listProjectNames().then(p => setProjects(p as any)).catch(console.error);
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
    // Load results — if the project has results, always show the active view
    projectSearchApi.getProjectResults(projectId).then(data => {
      setProjectResults(data.items);
      if (data.items.length > 0 || saved.length > 0) {
        setHasSearched(true);
        setPipelineStage('search_done');
      } else {
        setHasSearched(false);
      }
    }).catch(() => {
      setHasSearched(saved.length > 0);
    });
    projectSearchApi.getProjectSpending(projectId).then(setProjectSpending).catch(() => {});
    pipelineApi.getAutoEnrichConfig(projectId).then(setAutoEnrichConfig).catch(() => {});
  }, [setWebSearchProjectId]);

  // Generate system messages from SSE target data
  const handleSSEProgressWithTargets = useCallback((event: SearchProgressEvent) => {
    setProjectProgress(event);

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
      // Load final results
      if (webSearchProjectId) {
        projectSearchApi.getProjectResults(webSearchProjectId).then(data => setProjectResults(data.items));
        projectSearchApi.getProjectSpending(webSearchProjectId).then(setProjectSpending);
      }
      // Summary message — dedup (SSE sends both "progress" and terminal event)
      setWebSearchMessages(prev => {
        const alreadyDone = prev.some(m => m.id.startsWith('sys-done-'));
        if (alreadyDone) return prev;
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
        return [...prev, summaryMsg];
      });

      // Move pipeline to search_done and auto-trigger if configured
      if (event.phase === 'completed' && (event.targets_found || 0) > 0) {
        setPipelineStage('search_done');
      }
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
    } catch (error) {
      console.error('Cancel failed:', error);
    }
  }, [projectSearchJobId]);

  // Pipeline stage handlers — must be defined BEFORE the useEffects that reference them
  const handleExtractContacts = useCallback(async () => {
    if (!webSearchProjectId || pipelineStage !== 'search_done') return;
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
    }
  }, [webSearchProjectId, pipelineStage, autoEnrichConfig]);

  const handleEnrichApollo = useCallback(async () => {
    if (!webSearchProjectId || pipelineStage !== 'contacts_done') return;
    setPipelineStage('enrichment');
    setEnrichProgress('Starting...');
    try {
      const result = await pipelineApi.enrichApolloForProject(
        webSearchProjectId,
        autoEnrichConfig ?? undefined,
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
        jobId: projectSearchJobId || undefined,
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
        // Refresh sidebar to show new project
        contactsApi.listProjectNames().then(list => setSearchHistory(list as any)).catch(() => {});
      }

      // If search was started, begin SSE streaming
      if (response.action === 'search_started' && response.job_id) {
        setProjectSearchJobId(response.job_id);
        setIsProjectSearching(true);
        setProjectProgress(null);
        setProjectResults([]);
        setProjectSpending(null);
        setLastSeenTargets([]);
        setPipelineStage('searching');

        // Fetch auto-enrich config for the project
        const pid = response.project_id || webSearchProjectId;
        if (pid) {
          pipelineApi.getAutoEnrichConfig(pid).then(setAutoEnrichConfig).catch(() => setAutoEnrichConfig(null));
        }

        eventSourceRef.current?.close();
        const es = projectSearchApi.streamSearchJob(
          response.job_id,
          handleSSEProgressWithTargets,
          () => setIsProjectSearching(false),
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
  }, [webSearchQuery, isWebSearching, webSearchMessages, webSearchProjectId, projectSearchJobId, maxQueries, targetGoal, handleSSEProgressWithTargets]);

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

      // If no results found in DB, suggest switching to Web Search
      if (response.total === 0 && response.results.length === 0) {
        const suggestMsg: ChatMessage = {
          id: `sys-${Date.now()}`,
          role: 'system',
          content: 'No companies found in the database. Try switching to the "Web Search" tab to discover new companies from the web.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, suggestMsg]);
      }
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
    setIsProjectSearching(false);
    setExpandedResultId(null);
    // Reset web search state
    setWebSearchMessages([]);
    setWebSearchQuery('');
    setWebSearchProjectId(null);
    setWebSearchSuggestions([]);
    setLastSeenTargets([]);
    // Reset pipeline state
    setPipelineStage('idle');
    setContactsProgress(null);
    setEnrichProgress(null);
    setAutoEnrichConfig(null);
    eventSourceRef.current?.close();
    // Refresh sidebar
    contactsApi.listProjectNames().then(list => setSearchHistory(list as any)).catch(() => {});
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
      <AnimatedBackground />

      {/* Mode toggle + actions bar (no sub-header label to avoid double header) */}
      <div className="bg-white/80 backdrop-blur-md border-b border-gray-100 flex items-center px-6 py-2 sticky top-0 z-40">
        {/* Sidebar toggle */}
        {searchMode === 'project' && (
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="mr-3 p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          >
            {sidebarOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
          </button>
        )}
        {/* Mode Toggle — always visible */}
        <div className="flex items-center bg-gray-100 rounded-xl p-1">
          <button
            onClick={() => { setSearchMode('project'); if (hasSearched && searchMode !== 'project') handleNewSearch(); }}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all duration-200",
              searchMode === 'project'
                ? "bg-white text-emerald-600 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <Globe className="w-4 h-4" />
            Search
          </button>
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
            Database
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
            /* Chat + Results artifact (like Claude's artifacts) */
            <div className="flex-1 flex overflow-hidden">
              {/* Chat panel — full width when no results, narrower when results exist */}
              <div className={cn(
                "flex flex-col bg-white",
                projectResults.length > 0 || isProjectSearching
                  ? "w-[480px] border-r border-gray-100 flex-shrink-0"
                  : "flex-1"
              )}>
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

                {/* Pipeline stage indicator */}
                {pipelineStage !== 'idle' && (
                  <PipelineStageIndicator
                    stage={pipelineStage}
                    contactsProgress={contactsProgress}
                    enrichProgress={enrichProgress}
                    onExtractContacts={handleExtractContacts}
                    onEnrichApollo={handleEnrichApollo}
                    autoConfig={autoEnrichConfig}
                  />
                )}

                {/* Progress bar */}
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
                <div className="flex-1 overflow-y-auto">
                  <div className={cn(
                    "py-6 space-y-4",
                    projectResults.length > 0 || isProjectSearching ? "px-4" : "max-w-2xl mx-auto px-6"
                  )}>
                    {webSearchMessages.length === 0 && !isProjectSearching && (
                      <div className="flex flex-col items-center pt-20 text-center">
                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center mb-4">
                          <Bot className="w-7 h-7 text-emerald-600" />
                        </div>
                        <h3 className="text-lg font-semibold text-gray-700 mb-1">What are you looking for?</h3>
                        <p className="text-sm text-gray-400 max-w-sm">Describe target companies and I'll search the web to find them</p>
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
                <div className={cn("p-4 border-t border-gray-100 bg-white", !(projectResults.length > 0 || isProjectSearching) && "pb-8")}>
                  <div className={cn("relative", !(projectResults.length > 0 || isProjectSearching) && "max-w-2xl mx-auto")}>
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

              {/* Results artifact panel — slides in when results exist */}
              {(projectResults.length > 0 || isProjectSearching) && (
                <div className="flex-1 flex flex-col overflow-hidden bg-gray-50/50">
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
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                          <span title={`Yandex: $${projectSpending.yandex_cost.toFixed(3)} | Gemini: $${(projectSpending.gemini_cost_estimate ?? 0).toFixed(3)} | OpenAI: $${projectSpending.openai_cost_estimate.toFixed(3)} | Crona: ${projectSpending.crona_credits_used} credits`}>
                            Cost: <span className="text-gray-600 font-medium">${projectSpending.total_estimate.toFixed(2)}</span>
                          </span>
                        </div>
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
                                      <span className="px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700 rounded-full">Target</span>
                                    ) : (
                                      <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 rounded-full">Not Target</span>
                                    )}
                                    {result.confidence != null && (
                                      <span className="text-xs text-gray-500">{Math.round(result.confidence * 100)}%</span>
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
                        <h3 className="text-lg font-semibold text-gray-700 mb-2">Searching the web...</h3>
                        <p className="text-gray-500 text-sm max-w-sm">Results will appear here as websites are analyzed.</p>
                      </div>
                    ) : null}
                  </div>
                </div>
              )}
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
            ) : null}
          </div>
        ) : (
          // Search results state - chat + results (database/reverse modes)
          <div className="flex-1 flex flex-col max-w-7xl mx-auto w-full">
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
    </div>{/* end main content area */}
    </div>
  );
}

export default DataSearchPage;
