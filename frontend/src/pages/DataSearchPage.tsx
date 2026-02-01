import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
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
  ChevronRight,
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
} from 'lucide-react';
import { cn } from '../lib/utils';
import type { SearchFilter, CompanyResult, ChatMessage, ExtractedPattern, VerificationCriteria } from '../api/dataSearch';
import { dataSearchApi } from '../api/dataSearch';

// Search modes
type SearchMode = 'chat' | 'reverse';

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
  const navigate = useNavigate();
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

  // Scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex flex-col relative">
      <AnimatedBackground />
      
      {/* Header */}
      <header className="h-16 bg-white/80 backdrop-blur-md border-b border-gray-100 flex items-center px-6 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-bold text-gray-900 text-lg tracking-tight">
              Data Search
            </span>
            <p className="text-xs text-gray-500">AI-powered company discovery</p>
          </div>
        </div>

        {/* Mode Toggle */}
        {!hasSearched && (
          <div className="ml-8 flex items-center bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setSearchMode('chat')}
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
              onClick={() => setSearchMode('reverse')}
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
        )}

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

        <button
          onClick={() => navigate('/companies')}
          className="text-sm text-gray-600 hover:text-indigo-600 flex items-center gap-1.5 font-medium transition-colors"
        >
          Companies
          <ChevronRight className="w-4 h-4" />
        </button>
      </header>

      {/* Main content */}
      <main className="flex-1 flex flex-col max-w-7xl mx-auto w-full relative z-10">
        {!hasSearched ? (
          // Initial state
          <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
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
            ) : (
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
            )}
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
  );
}

export default DataSearchPage;
