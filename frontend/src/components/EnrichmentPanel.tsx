import { useState, useEffect, useCallback, useRef } from 'react';
import { Play, Loader2, ChevronDown, Sparkles, Building2, Target, Mic2, Trophy, DollarSign, Calendar, Swords, FileText, Mail, Users, FileStack, X, Search, CheckCircle, Linkedin, UserSearch, Globe } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { templatesApi, enrichmentApi, integrationsApi } from '../api';
import * as kbApi from '../api/knowledgeBase';
import { JobProgressCard } from './JobProgressCard';
import type { EnrichmentJob } from '../types';

// Enrichment action types
type EnrichmentAction = 
  | 'ai' 
  | 'scrape_website'
  | 'findymail_find_email' 
  | 'findymail_linkedin'
  | 'millionverifier_verify';

interface EnrichmentOption {
  id: EnrichmentAction;
  name: string;
  description: string;
  icon: React.ElementType;
  image?: string;
  price?: string;
  requiresConnection?: string;
}

const ENRICHMENT_OPTIONS: EnrichmentOption[] = [
  {
    id: 'ai',
    name: 'AI Enrichment',
    description: 'Custom prompts with GPT',
    icon: Sparkles,
    price: 'From $0.0001',
  },
  {
    id: 'scrape_website',
    name: 'Scrape Website',
    description: 'Extract text from websites',
    icon: Globe,
    price: 'Free',
  },
  {
    id: 'findymail_find_email',
    name: 'Find Email',
    description: 'By name + company domain',
    icon: UserSearch,
    image: '/findymail.png',
    price: '$0.025/email',
    requiresConnection: 'findymail',
  },
  {
    id: 'findymail_linkedin',
    name: 'Find by LinkedIn',
    description: 'By LinkedIn profile URL',
    icon: Linkedin,
    image: '/findymail.png',
    price: '$0.025/email',
    requiresConnection: 'findymail',
  },
  {
    id: 'millionverifier_verify',
    name: 'Verify Email',
    description: 'MillionVerifier validation',
    icon: CheckCircle,
    image: '/millionverifier.png',
    price: '$0.0004/email',
    requiresConnection: 'millionverifier',
  },
];

const TAG_ICONS: Record<string, React.ReactNode> = {
  company: <Building2 className="w-3.5 h-3.5" />,
  segment: <Target className="w-3.5 h-3.5" />,
  voice: <Mic2 className="w-3.5 h-3.5" />,
  case: <Trophy className="w-3.5 h-3.5" />,
  pricing: <DollarSign className="w-3.5 h-3.5" />,
  booking: <Calendar className="w-3.5 h-3.5" />,
  competitor: <Swords className="w-3.5 h-3.5" />,
  document: <FileText className="w-3.5 h-3.5" />,
  sequence: <Mail className="w-3.5 h-3.5" />,
  client: <Users className="w-3.5 h-3.5" />,
  summary: <FileStack className="w-3.5 h-3.5" />,
};

const TAG_COLORS: Record<string, string> = {
  company: 'bg-blue-100 text-blue-700',
  segment: 'bg-purple-100 text-purple-700',
  voice: 'bg-green-100 text-green-700',
  case: 'bg-yellow-100 text-yellow-700',
  pricing: 'bg-pink-100 text-pink-700',
  booking: 'bg-orange-100 text-orange-700',
  competitor: 'bg-red-100 text-red-700',
  document: 'bg-gray-100 text-gray-700',
  sequence: 'bg-indigo-100 text-indigo-700',
  client: 'bg-teal-100 text-teal-700',
  summary: 'bg-black text-white',
};

interface EnrichmentPanelProps {
  datasetId: number;
  columns: string[];
  onJobStarted: () => void;
  onColumnCreated?: () => void;
  startInCreateMode?: boolean;
  editColumnName?: string | null;
  onClose?: () => void;
}

const AVAILABLE_MODELS = [
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', cost: 0.00015 },
  { id: 'gpt-4o', name: 'GPT-4o', cost: 0.005 },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', cost: 0.01 },
  { id: 'o3-mini', name: 'o3-mini', cost: 0.002 },
];

function generateUniqueColumnName(existingColumns: string[], baseName: string = 'new_column'): string {
  const normalizedBase = baseName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
  if (!existingColumns.includes(normalizedBase)) return normalizedBase;
  let counter = 1;
  while (existingColumns.includes(`${normalizedBase}_${counter}`)) counter++;
  return `${normalizedBase}_${counter}`;
}

export function EnrichmentPanel({ datasetId, columns, onJobStarted, onColumnCreated, startInCreateMode = false, editColumnName, onClose }: EnrichmentPanelProps) {
  const { selectedRowIds, rows, templates, setTemplates } = useAppStore();
  
  // Action selection
  const [selectedAction, setSelectedAction] = useState<EnrichmentAction | null>(null);
  
  // Form state - AI
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [prompt, setPrompt] = useState('');
  const [outputColumn, setOutputColumn] = useState('');
  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini');
  
  // Form state - Scraper
  const [urlColumn, setUrlColumn] = useState('');
  
  // Form state - Findymail
  const [firstNameColumn, setFirstNameColumn] = useState('');
  const [lastNameColumn, setLastNameColumn] = useState('');
  const [fullNameColumn, setFullNameColumn] = useState('');
  const [useFullName, setUseFullName] = useState(true);
  const [domainColumn, setDomainColumn] = useState('');
  const [emailColumn, setEmailColumn] = useState('');
  const [linkedinColumn, setLinkedinColumn] = useState('');
  const [findymailConnected, setFindymailConnected] = useState(false);
  const [millionverifierConnected, setMillionverifierConnected] = useState(false);
  
  // UI state
  const [isCreating, setIsCreating] = useState(startInCreateMode);
  const [isEditingExisting, setIsEditingExisting] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showRunPopup, setShowRunPopup] = useState(false);
  const [recentJobs, setRecentJobs] = useState<EnrichmentJob[]>([]);
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const [columnPickerPosition, setColumnPickerPosition] = useState({ top: 0, left: 0 });
  const [columnFilter, setColumnFilter] = useState('');
  const [slashPosition, setSlashPosition] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Array<{ input: string; result: string; success: boolean }>>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [serviceSearch, setServiceSearch] = useState('');
  const [isEnhancing, setIsEnhancing] = useState(false);
  
  // KB Tags state
  const [kbTags, setKbTags] = useState<kbApi.KBTag[]>([]);
  const [showTagPicker, setShowTagPicker] = useState(false);
  const [tagFilter, setTagFilter] = useState('');
  const [atPosition, setAtPosition] = useState<number | null>(null);
  const [tagPickerPosition, setTagPickerPosition] = useState({ top: 0, left: 0 });
  
  const promptRef = useRef<HTMLTextAreaElement>(null);
  
  // Load KB tags
  useEffect(() => {
    kbApi.getAvailableTags().then(data => setKbTags(data.tags)).catch(console.error);
  }, []);

  // Check Findymail connection
  useEffect(() => {
    integrationsApi.getFindymail()
      .then(data => setFindymailConnected(data.connected))
      .catch(() => setFindymailConnected(false));
    
    integrationsApi.getMillionverifier()
      .then(data => setMillionverifierConnected(data.connected))
      .catch(() => setMillionverifierConnected(false));
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const jobs = await enrichmentApi.listJobs(datasetId);
      setRecentJobs(jobs.slice(0, 10));
    } catch (err) {
      console.error('Failed to load jobs:', err);
    }
  }, [datasetId]);

  useEffect(() => {
    loadTemplates();
    loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    if (startInCreateMode) {
      setIsCreating(true);
      setOutputColumn(generateUniqueColumnName(columns));
    }
  }, [startInCreateMode]);

  useEffect(() => {
    if (selectedTemplateId) {
      const template = templates.find(t => t.id === selectedTemplateId);
      if (template) {
        setOutputColumn(template.output_column);
        setPrompt(template.prompt_template);
      }
    }
  }, [selectedTemplateId, templates]);

  useEffect(() => {
    if (isCreating && !outputColumn) {
      setOutputColumn(generateUniqueColumnName(columns));
    }
  }, [isCreating, columns]);

  // Load existing column settings when editing
  useEffect(() => {
    if (editColumnName && recentJobs.length > 0) {
      // Find the most recent job for this column
      const job = recentJobs.find(j => j.output_column === editColumnName);
      if (job) {
        setIsCreating(true);
        setIsEditingExisting(true);
        setSelectedAction('ai');
        setPrompt(job.custom_prompt || '');
        setOutputColumn(job.output_column);
        setSelectedModel(job.model || 'gpt-4o-mini');
        setTestResults([]);
      }
    }
  }, [editColumnName, recentJobs]);

  const loadTemplates = async () => {
    try {
      const data = await templatesApi.list();
      setTemplates(data);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  };

  const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPos = e.target.selectionStart;
    setPrompt(value);
    
    // Handle / for columns
    if (value[cursorPos - 1] === '/') {
      const rect = e.target.getBoundingClientRect();
      setColumnPickerPosition({ top: rect.top + 30, left: rect.left + 10 });
      setSlashPosition(cursorPos - 1);
      setShowColumnPicker(true);
      setColumnFilter('');
      setShowTagPicker(false);
    } else if (showColumnPicker && slashPosition !== null) {
      const filterText = value.slice(slashPosition + 1, cursorPos);
      if (filterText.includes(' ') || filterText.includes('\n')) {
        setShowColumnPicker(false);
        setSlashPosition(null);
      } else {
        setColumnFilter(filterText);
      }
    }
    
    // Handle @ for KB tags
    if (value[cursorPos - 1] === '@') {
      const rect = e.target.getBoundingClientRect();
      setTagPickerPosition({ top: rect.top + 30, left: rect.left + 10 });
      setAtPosition(cursorPos - 1);
      setShowTagPicker(true);
      setTagFilter('');
      setShowColumnPicker(false);
    } else if (showTagPicker && atPosition !== null) {
      const filterText = value.slice(atPosition + 1, cursorPos);
      if (filterText.includes(' ') || filterText.includes('\n')) {
        setShowTagPicker(false);
        setAtPosition(null);
      } else {
        setTagFilter(filterText);
      }
    }
  };
  
  const insertTag = (tag: kbApi.KBTag) => {
    if (atPosition !== null) {
      const textBefore = prompt.slice(0, atPosition);
      const cursorPos = promptRef.current?.selectionStart || prompt.length;
      const textAfter = prompt.slice(cursorPos);
      setPrompt(textBefore + tag.tag + ' ' + textAfter);
    }
    setShowTagPicker(false);
    setAtPosition(null);
  };
  
  const filteredTags = kbTags.filter(tag => 
    tag.tag.toLowerCase().includes(tagFilter.toLowerCase()) ||
    tag.label.toLowerCase().includes(tagFilter.toLowerCase())
  );

  const insertColumn = (column: string) => {
    if (slashPosition !== null) {
      const textBefore = prompt.slice(0, slashPosition);
      const cursorPos = promptRef.current?.selectionStart || prompt.length;
      const textAfter = prompt.slice(cursorPos);
      setPrompt(textBefore + `{{${column}}}` + textAfter);
    }
    setShowColumnPicker(false);
    setSlashPosition(null);
  };

  const handleEnhancePrompt = async () => {
    if (!prompt.trim() || isEnhancing) return;
    
    setIsEnhancing(true);
    try {
      const result = await enrichmentApi.enhancePrompt({
        rough_prompt: prompt,
        columns: columns,
        output_description: '',
      });
      
      setPrompt(result.enhanced_prompt);
      
      // Only update output column if it's still the default
      if (!outputColumn || outputColumn.startsWith('new_column')) {
        setOutputColumn(generateUniqueColumnName(columns, result.suggested_output_column));
      }
    } catch (err: any) {
      console.error('Failed to enhance prompt:', err);
    } finally {
      setIsEnhancing(false);
    }
  };

  const handleTest = async () => {
    if (!prompt) return;
    setIsTesting(true);
    setTestResults([]);
    
    try {
      const testRows = rows.slice(0, 5);
      const response = await enrichmentApi.preview({
        dataset_id: datasetId,
        custom_prompt: prompt,
        output_column: outputColumn || 'test',
        model: selectedModel,
        row_ids: testRows.map(r => r.id),
      });
      
      const results = response.results.map((r: any, idx: number) => ({
        input: Object.values(testRows[idx]?.data || {}).slice(0, 2).join(', '),
        result: r.success ? r.result : r.error,
        success: r.success,
      }));
      setTestResults(results);
    } catch (err: any) {
      setTestResults([{ input: '', result: err.message || 'Test failed', success: false }]);
    } finally {
      setIsTesting(false);
    }
  };

  const handleRun = async (count: number) => {
    if (!outputColumn || !selectedAction) return;
    
    setShowRunPopup(false);
    
    let finalColumnName = outputColumn;
    // Only generate a new column name if we're not editing an existing column
    if (!isEditingExisting && columns.includes(outputColumn)) {
      finalColumnName = generateUniqueColumnName(columns, outputColumn);
      setOutputColumn(finalColumnName);
    }
    
    setIsRunning(true);
    try {
      const rowIds = selectedRowIds.size > 0 
        ? Array.from(selectedRowIds).slice(0, count)
        : rows.slice(0, count).map(r => r.id);

      if (selectedAction === 'ai') {
        const job = await enrichmentApi.createJob({
        dataset_id: datasetId,
          custom_prompt: prompt,
          output_column: finalColumnName,
        model: selectedModel,
          selected_row_ids: rowIds,
        });
        
        const model = AVAILABLE_MODELS.find(m => m.id === selectedModel);
        if (model) {
          window.dispatchEvent(new CustomEvent('api-cost-update', { 
            detail: { cost: model.cost * rowIds.length, datasetId, source: 'openai' } 
          }));
        }
        
        setRecentJobs(prev => [job, ...prev.slice(0, 9)]);
      } else if (selectedAction === 'findymail_find_email') {
        const nameCol = useFullName ? fullNameColumn : `${firstNameColumn}+${lastNameColumn}`;
        const result = await integrationsApi.findymailEnrich({
          dataset_id: datasetId,
          row_ids: rowIds,
          enrichment_type: 'find_email',
          output_column: finalColumnName,
          name_column: nameCol,
          domain_column: domainColumn,
        });
        
        window.dispatchEvent(new CustomEvent('api-cost-update', { 
          detail: { cost: result.total_cost, datasetId, source: 'findymail' } 
        }));
        
        // Wait for background task to complete before refresh
        await new Promise(resolve => setTimeout(resolve, 3000 + rowIds.length * 500));
      } else if (selectedAction === 'findymail_linkedin') {
        const result = await integrationsApi.findymailEnrich({
          dataset_id: datasetId,
          row_ids: rowIds,
          enrichment_type: 'find_by_linkedin',
          output_column: finalColumnName,
          email_column: linkedinColumn, // Reusing email_column for linkedin
        });
        
        window.dispatchEvent(new CustomEvent('api-cost-update', { 
          detail: { cost: result.total_cost, datasetId, source: 'findymail' } 
        }));
        
        // Wait for background task to complete before refresh
        await new Promise(resolve => setTimeout(resolve, 3000 + rowIds.length * 500));
      } else if (selectedAction === 'millionverifier_verify') {
        await integrationsApi.millionverifierVerify({
          dataset_id: datasetId,
          row_ids: rowIds,
          email_column: emailColumn,
          output_column: finalColumnName,
        });
        
        // Cost is very low for millionverifier (~$0.0004/email)
        window.dispatchEvent(new CustomEvent('api-cost-update', { 
          detail: { cost: rowIds.length * 0.0004, datasetId, source: 'millionverifier' } 
        }));
        
        // Wait for background task to complete before refresh
        await new Promise(resolve => setTimeout(resolve, 2000 + rowIds.length * 50));
      } else if (selectedAction === 'scrape_website') {
        await enrichmentApi.scrapeWebsites({
          dataset_id: datasetId,
          row_ids: rowIds,
          url_column: urlColumn,
          output_column: finalColumnName,
          timeout: 10,
        });
        
        // Wait for background task to complete before refresh
        await new Promise(resolve => setTimeout(resolve, 2000 + rowIds.length * 1000));
      }
      
      setIsCreating(false);
      resetForm();
      onJobStarted();
      onColumnCreated?.();
    } catch (err) {
      console.error('Job creation failed:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSaveTemplate = async () => {
    if (!templateName || !prompt || !outputColumn) return;
    try {
      await templatesApi.create({
        name: templateName,
        prompt_template: prompt,
        output_column: outputColumn,
      });
      await loadTemplates();
      setShowSaveModal(false);
      setTemplateName('');
    } catch (err) {
      console.error('Failed to save template:', err);
    }
  };

  const handleStopJob = async (jobId: number) => {
    try {
      await enrichmentApi.stopJob(jobId);
      loadJobs();
    } catch (err) {
      console.error('Failed to stop job:', err);
    }
  };

  const resetForm = () => {
    setSelectedTemplateId(null);
    setPrompt('');
    setOutputColumn('');
    setTestResults([]);
    setUrlColumn('');
    setFirstNameColumn('');
    setLastNameColumn('');
    setFullNameColumn('');
    setDomainColumn('');
    setEmailColumn('');
    setLinkedinColumn('');
    setSelectedAction(null);
    setIsEditingExisting(false);
  };

  const canRun = outputColumn && selectedAction && (
    (selectedAction === 'ai' && prompt) ||
    (selectedAction === 'scrape_website' && urlColumn) ||
    (selectedAction === 'findymail_find_email' && findymailConnected && (
      (useFullName ? fullNameColumn : (firstNameColumn && lastNameColumn)) && domainColumn
    )) ||
    (selectedAction === 'findymail_linkedin' && findymailConnected && linkedinColumn) ||
    (selectedAction === 'millionverifier_verify' && millionverifierConnected && emailColumn)
  );
  const filteredColumns = columns.filter(c => c.toLowerCase().includes(columnFilter.toLowerCase()));

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-orange-500" />
          <span className="text-sm font-medium text-neutral-900">Enrich</span>
        </div>
        <div className="flex items-center gap-2">
          {!isCreating && (
            <button onClick={() => setIsCreating(true)} className="text-xs text-neutral-600 hover:text-neutral-900">
              + New
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="p-1 hover:bg-neutral-100 rounded transition-colors">
              <X className="w-4 h-4 text-neutral-400" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {/* Create form */}
        {isCreating && (
          <div className="p-4 space-y-4 border-b border-neutral-100">
            {/* Action Selection - Scrollable cards with search */}
            {!selectedAction && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-neutral-500 uppercase tracking-wide">Choose enrichment type</p>
                
                {/* Search input */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                  <input
                    type="text"
                    value={serviceSearch}
                    onChange={(e) => setServiceSearch(e.target.value)}
                    placeholder="Search services..."
                    className="w-full text-sm border border-neutral-200 rounded-lg pl-9 pr-3 py-2"
                    autoFocus
                  />
                </div>
                
                {/* Services list */}
                <div className="space-y-2 overflow-y-auto pr-1" style={{ maxHeight: 'calc(100vh - 320px)' }}>
                  {ENRICHMENT_OPTIONS
                    .filter(option => 
                      serviceSearch === '' ||
                      option.name.toLowerCase().includes(serviceSearch.toLowerCase()) ||
                      option.description.toLowerCase().includes(serviceSearch.toLowerCase())
                    )
                    .map((option) => {
                      const isDisabled = 
                        (option.requiresConnection === 'findymail' && !findymailConnected) ||
                        (option.requiresConnection === 'millionverifier' && !millionverifierConnected);
                      return (
                        <button
                          key={option.id}
                          onClick={() => {
                            setSelectedAction(option.id);
                            setServiceSearch('');
                            // Set default output column based on action
                            if (option.id === 'findymail_find_email' || option.id === 'findymail_linkedin') {
                              setOutputColumn(generateUniqueColumnName(columns, 'email'));
                            } else if (option.id === 'millionverifier_verify') {
                              setOutputColumn(generateUniqueColumnName(columns, 'email_verified'));
                            } else if (option.id === 'scrape_website') {
                              setOutputColumn(generateUniqueColumnName(columns, 'website_text'));
                            } else {
                              setOutputColumn(generateUniqueColumnName(columns, 'new_column'));
                            }
                          }}
                          disabled={isDisabled}
                          className={cn(
                            'w-full flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-all',
                            'border-neutral-200 hover:border-neutral-400 hover:bg-neutral-50',
                            isDisabled && 'opacity-50 cursor-not-allowed'
                          )}
                        >
                          <div className={cn(
                            'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 overflow-hidden',
                            option.id === 'ai' ? 'bg-gradient-to-br from-violet-500 to-purple-600' : 'bg-neutral-100'
                          )}>
                            {option.image ? (
                              <img src={option.image} alt={option.name} className="w-10 h-10 object-cover" />
                            ) : (
                              <option.icon className={cn('w-5 h-5', option.id === 'ai' ? 'text-white' : 'text-neutral-600')} />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-neutral-900">{option.name}</div>
                            <div className="text-xs text-neutral-500">{option.description}</div>
                          </div>
                          {option.price && (
                            <span className="text-xs text-neutral-400 flex-shrink-0">{option.price}</span>
                          )}
                        </button>
                      );
                    })}
                  
                  {ENRICHMENT_OPTIONS.filter(option => 
                    serviceSearch === '' ||
                    option.name.toLowerCase().includes(serviceSearch.toLowerCase()) ||
                    option.description.toLowerCase().includes(serviceSearch.toLowerCase())
                  ).length === 0 && (
                    <p className="text-sm text-neutral-400 text-center py-4">No services found</p>
                  )}
                </div>
                
                {!findymailConnected && (
                  <p className="text-xs text-neutral-400 mt-2">
                    Connect Findymail in Settings to enable email search
                  </p>
                )}
                {!millionverifierConnected && (
                  <p className="text-xs text-neutral-400 mt-2">
                    Connect MillionVerifier in Settings to enable email verification
                  </p>
                )}
              </div>
            )}

            {/* Selected action header */}
            {selectedAction && (
              <button
                onClick={() => setSelectedAction(null)}
                className="flex items-center gap-2 text-xs text-neutral-500 hover:text-neutral-700"
              >
                <X className="w-3 h-3" />
                Change action
              </button>
            )}

            {/* AI Form */}
            {selectedAction === 'ai' && (
              <>
                {/* Template */}
                <select
                  value={selectedTemplateId || ''}
                  onChange={(e) => setSelectedTemplateId(Number(e.target.value) || null)}
                  className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                >
                  <option value="">Custom prompt</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>

                {/* Prompt */}
                <div>
                  <div className="relative">
                    <textarea
                      ref={promptRef}
                      value={prompt}
                      onChange={handlePromptChange}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') { setShowColumnPicker(false); setSlashPosition(null); }
                        if (e.key === 'Enter' && showColumnPicker && filteredColumns.length > 0) {
                          e.preventDefault();
                          insertColumn(filteredColumns[0]);
                        }
                      }}
                      placeholder="Write in any language... AI will optimize your prompt"
                      className={cn(
                        "w-full text-sm border border-neutral-200 rounded-lg px-3 py-2 min-h-[160px] resize-y font-mono",
                        isEnhancing && "opacity-50"
                      )}
                      disabled={isEnhancing}
                    />
                    {isEnhancing && (
                      <div className="absolute inset-0 flex items-center justify-center bg-white/80 rounded-lg">
                        <div className="flex flex-col items-center gap-2">
                          <div className="flex items-center gap-1">
                            <div className="w-2 h-2 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                          <span className="text-sm text-violet-600 font-medium">AI is writing your prompt...</span>
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center justify-between mt-1.5">
                    <p className="text-xs text-neutral-400">Type <kbd className="px-1 bg-neutral-100 rounded">/</kbd> for columns</p>
                    <button
                      onClick={handleEnhancePrompt}
                      disabled={!prompt.trim() || isEnhancing}
                      className={cn(
                        'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all',
                        prompt.trim() && !isEnhancing
                          ? 'bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:from-violet-600 hover:to-purple-700 shadow-sm'
                          : 'bg-neutral-100 text-neutral-400 cursor-not-allowed'
                      )}
                    >
                      <Sparkles className="w-3 h-3" />
                      <span>Enhance with AI</span>
                    </button>
                  </div>
                </div>

                {/* Model */}
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                >
                  {AVAILABLE_MODELS.map(m => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </>
            )}

            {/* Scrape Website Form */}
            {selectedAction === 'scrape_website' && (
              <div>
                <label className="text-xs text-neutral-500 mb-1 block">Website URL column *</label>
                <select
                  value={urlColumn}
                  onChange={(e) => setUrlColumn(e.target.value)}
                  className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                >
                  <option value="">Select column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                <p className="text-xs text-neutral-400 mt-1">Column with website URLs (e.g. acme.com or https://acme.com)</p>
              </div>
            )}

            {/* Find Email Form */}
            {selectedAction === 'findymail_find_email' && (
              <>
                {/* Name type toggle */}
                <div className="flex gap-2 p-1 bg-neutral-100 rounded-lg">
        <button
                    onClick={() => setUseFullName(true)}
          className={cn(
                      'flex-1 text-xs py-1.5 rounded-md transition-all',
                      useFullName ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600'
                    )}
                  >
                    Full Name
        </button>
        <button
                    onClick={() => setUseFullName(false)}
          className={cn(
                      'flex-1 text-xs py-1.5 rounded-md transition-all',
                      !useFullName ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-600'
                    )}
                  >
                    First + Last
        </button>
      </div>

                {useFullName ? (
                  <div>
                    <label className="text-xs text-neutral-500 mb-1 block">Full name column *</label>
                    <select
                      value={fullNameColumn}
                      onChange={(e) => setFullNameColumn(e.target.value)}
                      className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                    >
                      <option value="">Select column...</option>
                      {columns.map(col => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-neutral-500 mb-1 block">First name *</label>
                      <select
                        value={firstNameColumn}
                        onChange={(e) => setFirstNameColumn(e.target.value)}
                        className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                      >
                        <option value="">Select...</option>
                        {columns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-neutral-500 mb-1 block">Last name *</label>
                      <select
                        value={lastNameColumn}
                        onChange={(e) => setLastNameColumn(e.target.value)}
                        className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                      >
                        <option value="">Select...</option>
                        {columns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

        <div>
                  <label className="text-xs text-neutral-500 mb-1 block">Company domain column *</label>
            <select
                    value={domainColumn}
                    onChange={(e) => setDomainColumn(e.target.value)}
                    className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                  >
                    <option value="">Select column...</option>
                    {columns.map(col => (
                      <option key={col} value={col}>{col}</option>
              ))}
            </select>
                  <p className="text-xs text-neutral-400 mt-1">Can be domain (acme.com) or company name</p>
          </div>
              </>
            )}

            {/* Find by LinkedIn Form */}
            {selectedAction === 'findymail_linkedin' && (
              <div>
                <label className="text-xs text-neutral-500 mb-1 block">LinkedIn URL column *</label>
                <select
                  value={linkedinColumn}
                  onChange={(e) => setLinkedinColumn(e.target.value)}
                  className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                >
                  <option value="">Select column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                <p className="text-xs text-neutral-400 mt-1">e.g. linkedin.com/in/username</p>
        </div>
      )}

            {/* MillionVerifier Email Verification Form */}
            {selectedAction === 'millionverifier_verify' && (
        <div>
                <label className="text-xs text-neutral-500 mb-1 block">Email column to verify *</label>
                <select
                  value={emailColumn}
                  onChange={(e) => setEmailColumn(e.target.value)}
                  className="w-full text-sm border border-neutral-200 rounded-lg px-3 py-2"
                >
                  <option value="">Select column...</option>
                  {columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                <p className="text-xs text-neutral-400 mt-1">Results: ok, invalid, disposable, catch-all, etc.</p>
        </div>
      )}

            {/* Output column - only show when action selected */}
            {selectedAction && (
              <div>
                {isEditingExisting && (
                  <p className="text-xs text-orange-600 mb-1">Editing existing column - data will be overwritten</p>
                )}
                <input
                  type="text"
                  value={outputColumn}
                  onChange={(e) => setOutputColumn(e.target.value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, ''))}
                  placeholder="output_column"
                  disabled={isEditingExisting}
                  className={cn(
                    "w-full text-sm border border-neutral-200 rounded-lg px-3 py-2 font-mono",
                    isEditingExisting && "bg-neutral-100 cursor-not-allowed"
                  )}
                />
              </div>
            )}

            {/* Actions - only show when action selected */}
            {selectedAction && (
            <div className="flex gap-2">
              <button
                onClick={() => { setIsCreating(false); resetForm(); }}
                className="px-3 py-1.5 text-sm text-neutral-600 hover:text-neutral-900"
              >
                Cancel
              </button>
              {selectedAction === 'ai' && (
                <button
                  onClick={() => setShowSaveModal(true)}
                  disabled={!canRun}
                  className="px-3 py-1.5 text-sm text-neutral-600 hover:text-neutral-900 disabled:opacity-40"
                >
                  Save
                </button>
              )}
              <div className="relative flex-1">
                <button
                  onClick={() => setShowRunPopup(!showRunPopup)}
                  disabled={!canRun || isRunning}
                  className="w-full px-3 py-1.5 text-sm bg-black text-white rounded-lg flex items-center justify-center gap-2 disabled:opacity-40"
                >
                  {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                  Run
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
                {showRunPopup && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowRunPopup(false)} />
                    <div className="absolute right-0 top-full mt-1 z-50 bg-white rounded-lg border shadow-lg py-1 min-w-[100px]">
                      {[5, 15, 100, rows.length].map(n => (
                        <button
                          key={n}
                          onClick={() => handleRun(n)}
                          className="w-full px-3 py-1.5 text-sm text-left hover:bg-neutral-50"
                        >
                          {n === rows.length ? `All (${n})` : `${n} rows`}
                        </button>
                      ))}
                    </div>
                  </>
                )}
        </div>
      </div>
            )}

            {/* Test results inline - only for AI */}
            {(isTesting || testResults.length > 0) && (
              <div className="mt-3 p-3 bg-neutral-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-neutral-600">Test Results (5 rows)</span>
                  <button
                    onClick={handleTest}
                    disabled={isTesting || !prompt}
                    className="text-xs text-neutral-500 hover:text-neutral-700"
                  >
                    {isTesting ? 'Testing...' : 'Run test'}
                  </button>
                </div>
                {testResults.length > 0 && (
                  <div className="space-y-2">
                    {testResults.map((r, i) => (
                      <div key={i} className={cn(
                        "p-2 rounded text-xs",
                        r.success ? "bg-white border border-neutral-200" : "bg-red-50 border border-red-200"
                      )}>
                        <div className={r.success ? "text-neutral-800" : "text-red-700"}>
                          {r.result.slice(0, 200)}{r.result.length > 200 ? '...' : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {!testResults.length && !isTesting && (
                  <p className="text-xs text-neutral-400">Click "Run test" to preview results</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Column picker */}
        {showColumnPicker && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => { setShowColumnPicker(false); setSlashPosition(null); }} />
            <div
              className="fixed z-50 bg-white rounded-lg border shadow-lg w-48 max-h-48 overflow-auto"
              style={{ top: columnPickerPosition.top, left: columnPickerPosition.left }}
            >
              {filteredColumns.length > 0 ? (
                filteredColumns.map((col, idx) => (
                  <button
                    key={col}
                    onClick={() => insertColumn(col)}
                    className={cn(
                      "w-full text-left px-3 py-1.5 text-sm",
                      idx === 0 ? "bg-neutral-100" : "hover:bg-neutral-50"
                    )}
                  >
                    {col}
                  </button>
                ))
              ) : (
                <div className="px-3 py-2 text-sm text-neutral-400">No columns</div>
              )}
        </div>
          </>
        )}

        {/* KB Tag picker */}
        {showTagPicker && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => { setShowTagPicker(false); setAtPosition(null); }} />
            <div
              className="fixed z-50 bg-white rounded-lg border shadow-lg w-72 max-h-64 overflow-auto"
              style={{ top: tagPickerPosition.top, left: tagPickerPosition.left }}
            >
              <div className="px-3 py-2 text-xs text-neutral-500 border-b">Knowledge Base Tags</div>
              {filteredTags.length > 0 ? (
                filteredTags.map((tag, idx) => (
        <button
                    key={tag.tag}
                    onClick={() => insertTag(tag)}
                    className={cn(
                      "w-full text-left px-3 py-2 flex items-center gap-2",
                      idx === 0 ? "bg-neutral-100" : "hover:bg-neutral-50"
                    )}
                  >
                    <div className={cn("w-6 h-6 rounded flex items-center justify-center", TAG_COLORS[tag.type])}>
                      {TAG_ICONS[tag.type]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-neutral-900 truncate">{tag.label}</div>
                      <div className="text-xs text-neutral-500 truncate">{tag.tag}</div>
                    </div>
                  </button>
                ))
              ) : (
                <div className="px-3 py-4 text-sm text-neutral-400 text-center">
                  No tags found<br />
                  <span className="text-xs">Add data in Knowledge Base</span>
                </div>
              )}
            </div>
          </>
        )}

        {/* Save template modal */}
        {showSaveModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/20" onClick={() => setShowSaveModal(false)} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-sm p-4">
              <h3 className="font-medium mb-3">Save as Template</h3>
              <input
                type="text"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="Template name"
                className="w-full border rounded-lg px-3 py-2 text-sm mb-3"
                autoFocus
              />
              <div className="flex gap-2">
                <button onClick={() => setShowSaveModal(false)} className="flex-1 py-2 text-sm text-neutral-600">
                  Cancel
        </button>
        <button
                  onClick={handleSaveTemplate}
                  disabled={!templateName}
                  className="flex-1 py-2 text-sm bg-black text-white rounded-lg disabled:opacity-40"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Jobs - only show when not creating */}
        {!isCreating && recentJobs.length > 0 && (
          <div className="p-4">
            <div className="text-xs font-medium text-neutral-500 mb-2">Recent Jobs</div>
            <div className="space-y-2">
              {recentJobs.map((job) => (
                <JobProgressCard
                  key={job.id}
                  job={job}
                  onComplete={() => { loadJobs(); onJobStarted(); onColumnCreated?.(); }}
                  onStop={() => handleStopJob(job.id)}
                  onEdit={(j) => {
                    setPrompt(j.custom_prompt || '');
                    setOutputColumn(j.output_column);
                    setSelectedModel(j.model);
                    setSelectedAction('ai');
                    setIsEditingExisting(true);
                    setIsCreating(true);
                  }}
                  onRerun={(j) => {
                    setPrompt(j.custom_prompt || '');
                    setOutputColumn(j.output_column);
                    setSelectedModel(j.model);
                    setSelectedAction('ai');
                    setIsEditingExisting(true);
                    setShowRunPopup(true);
                    setIsCreating(true);
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isCreating && recentJobs.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center py-8">
              <Sparkles className="w-6 h-6 text-neutral-200 mx-auto mb-2" />
              <button
                onClick={() => setIsCreating(true)}
                className="text-xs text-neutral-500 hover:text-neutral-700"
              >
                Create column
        </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
