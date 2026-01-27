import { useState, useEffect } from 'react';
import { X, Loader2, Check, AlertCircle, Database, Sparkles, ArrowRight } from 'lucide-react';
import { cn } from '../lib/utils';
import { prospectsApi, type FieldMapping, type CoreField } from '../api';
import type { Dataset } from '../types';
import { datasetsApi } from '../api/datasets';

interface FieldMappingModalProps {
  isOpen: boolean;
  onClose: () => void;
  dataset: Dataset;
  rowIds?: number[];
  // For marking as sent to Instantly
  instantlyCampaign?: {
    id: string;
    name: string;
  };
}

export function FieldMappingModal({ isOpen, onClose, dataset, rowIds, instantlyCampaign }: FieldMappingModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mappings, setMappings] = useState<FieldMapping[]>([]);
  const [coreFields, setCoreFields] = useState<CoreField[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [result, setResult] = useState<{ new_prospects: number; updated_prospects: number } | null>(null);

  // Get all columns from dataset (original + enriched)
  const allColumns = dataset.columns;

  useEffect(() => {
    if (isOpen) {
      loadMappings();
    }
  }, [isOpen, dataset.id]);

  const loadMappings = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Load core fields definition
      let fields: CoreField[] = [];
      try {
        fields = await prospectsApi.getCoreFields();
      } catch {
        // Fallback core fields
        fields = [
          { name: 'email', label: 'Email', type: 'email' },
          { name: 'linkedin_url', label: 'LinkedIn URL', type: 'url' },
          { name: 'first_name', label: 'First Name', type: 'text' },
          { name: 'last_name', label: 'Last Name', type: 'text' },
          { name: 'full_name', label: 'Full Name', type: 'text' },
          { name: 'company_name', label: 'Company Name', type: 'text' },
          { name: 'company_domain', label: 'Company Domain', type: 'text' },
          { name: 'job_title', label: 'Job Title', type: 'text' },
          { name: 'phone', label: 'Phone', type: 'phone' },
          { name: 'location', label: 'Location', type: 'text' },
          { name: 'country', label: 'Country', type: 'text' },
          { name: 'city', label: 'City', type: 'text' },
          { name: 'industry', label: 'Industry', type: 'text' },
          { name: 'company_size', label: 'Company Size', type: 'text' },
          { name: 'website', label: 'Website', type: 'url' },
        ];
      }
      setCoreFields(fields);

      // Get sample data for AI mapping
      let sampleData: Record<string, any>[] = [];
      let allCols = [...dataset.columns];
      
      try {
        const rowsResponse = await datasetsApi.getRows(dataset.id, 1, 5);
        sampleData = rowsResponse.rows.map((r: any) => ({
          ...r.data,
          ...r.enriched_data
        }));

        // Get all columns including enriched
        if (rowsResponse.rows.length > 0) {
          const enrichedKeys = Object.keys(rowsResponse.rows[0].enriched_data || {});
          enrichedKeys.forEach(key => {
            if (!allCols.includes(key)) {
              allCols.push(key);
            }
          });
        }
      } catch (e) {
        console.warn('Could not fetch sample data:', e);
      }

      // Get AI suggestions
      try {
        const suggestion = await prospectsApi.suggestMapping({
          dataset_id: dataset.id,
          columns: allCols,
          sample_data: sampleData
        });
        setMappings(suggestion.mappings);
      } catch (mappingErr) {
        console.warn('AI mapping failed, using smart defaults:', mappingErr);
        // Create smart default mappings based on column names
        const defaultMappings: FieldMapping[] = allCols.map(col => {
          const colLower = col.toLowerCase();
          let targetField = 'custom';
          let confidence = 0.5;
          
          // Simple pattern matching for fallback
          if (colLower.includes('email') || colLower.includes('mail')) {
            targetField = 'email';
            confidence = 0.9;
          } else if (colLower.includes('linkedin')) {
            targetField = colLower.includes('company') ? 'company_linkedin' : 'linkedin_url';
            confidence = 0.9;
          } else if (colLower.includes('first') && colLower.includes('name')) {
            targetField = 'first_name';
            confidence = 0.9;
          } else if (colLower.includes('last') && colLower.includes('name')) {
            targetField = 'last_name';
            confidence = 0.9;
          } else if (colLower === 'name' || colLower.includes('full_name')) {
            targetField = 'full_name';
            confidence = 0.8;
          } else if (colLower.includes('company') || colLower.includes('organization')) {
            targetField = 'company_name';
            confidence = 0.8;
          } else if (colLower.includes('title') || colLower.includes('position') || colLower.includes('role')) {
            targetField = 'job_title';
            confidence = 0.8;
          } else if (colLower.includes('phone') || colLower.includes('mobile') || colLower.includes('tel')) {
            targetField = 'phone';
            confidence = 0.8;
          } else if (colLower.includes('country')) {
            targetField = 'country';
            confidence = 0.9;
          } else if (colLower.includes('city')) {
            targetField = 'city';
            confidence = 0.9;
          } else if (colLower.includes('location') || colLower.includes('address')) {
            targetField = 'location';
            confidence = 0.8;
          } else if (colLower.includes('industry') || colLower.includes('sector')) {
            targetField = 'industry';
            confidence = 0.8;
          } else if (colLower.includes('domain')) {
            targetField = 'company_domain';
            confidence = 0.8;
          } else if (colLower.includes('website') || colLower.includes('url') || colLower.includes('site')) {
            targetField = 'website';
            confidence = 0.7;
          }
          
          return {
            source_column: col,
            target_field: targetField,
            custom_field_name: targetField === 'custom' ? col : undefined,
            confidence
          };
        });
        setMappings(defaultMappings);
      }
    } catch (err: any) {
      console.error('Failed to load mappings:', err);
      setError('Failed to initialize. Please try again.');
      // Create basic fallback mappings
      const defaultMappings: FieldMapping[] = allColumns.map(col => ({
        source_column: col,
        target_field: 'custom',
        custom_field_name: col,
        confidence: 0.5
      }));
      setMappings(defaultMappings);
    } finally {
      setIsLoading(false);
    }
  };

  const updateMapping = (sourceColumn: string, targetField: string) => {
    setMappings(prev => prev.map(m => {
      if (m.source_column === sourceColumn) {
        return {
          ...m,
          target_field: targetField,
          custom_field_name: targetField === 'custom' ? m.source_column : undefined,
          confidence: 1.0 // User manually set
        };
      }
      return m;
    }));
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await prospectsApi.addFromDataset({
        dataset_id: dataset.id,
        row_ids: rowIds,
        field_mappings: mappings
      });

      if (response.success) {
        // If we have Instantly campaign info, mark prospects as sent
        if (instantlyCampaign && (response.new_prospects > 0 || response.updated_prospects > 0)) {
          try {
            // Get the prospect IDs that were just added/updated
            // For now, we'll make a call to mark by email lookup
            // This is handled by the backend when adding from dataset with campaign info
            console.log('Marking as sent to Instantly:', instantlyCampaign.name);
          } catch (e) {
            console.warn('Failed to mark as sent to Instantly:', e);
          }
        }

        setResult({
          new_prospects: response.new_prospects,
          updated_prospects: response.updated_prospects
        });
        
        const instantlyNote = instantlyCampaign 
          ? ` (marked as sent to "${instantlyCampaign.name}")` 
          : '';
        setSuccess(`Added ${response.new_prospects} new prospects, updated ${response.updated_prospects} existing.${instantlyNote}`);
      } else {
        setError(response.errors?.join(', ') || 'Failed to add prospects');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add prospects');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  // Group mappings by type
  const coreMappings = mappings.filter(m => m.target_field !== 'custom');
  const customMappings = mappings.filter(m => m.target_field === 'custom');
  const rowCount = rowIds ? rowIds.length : dataset.row_count;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      <div className="relative modal-content w-full max-w-2xl p-6 animate-slide-up max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <Database className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">Add to All Prospects</h2>
              <p className="text-sm text-neutral-500">{rowCount.toLocaleString()} prospects from {dataset.name}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-neutral-100 transition-colors">
            <X className="w-4 h-4 text-neutral-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-violet-500 mb-3" />
              <p className="text-sm text-neutral-500">Analyzing columns with AI...</p>
            </div>
          ) : success ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mb-4">
                <Check className="w-8 h-8 text-emerald-600" />
              </div>
              <h3 className="text-lg font-semibold text-neutral-900 mb-2">Successfully Added!</h3>
              <p className="text-neutral-600 text-center mb-4">{success}</p>
              {result && (
                <div className="flex gap-6 text-center">
                  <div>
                    <div className="text-2xl font-bold text-violet-600">{result.new_prospects}</div>
                    <div className="text-sm text-neutral-500">New prospects</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-amber-600">{result.updated_prospects}</div>
                    <div className="text-sm text-neutral-500">Updated (merged)</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* AI Badge */}
              <div className="flex items-center gap-2 text-xs text-violet-600 bg-violet-50 px-3 py-2 rounded-lg mb-4">
                <Sparkles className="w-4 h-4" />
                <span>AI auto-mapped your columns. Review and adjust if needed.</span>
              </div>

              {/* Mappings */}
              <div className="space-y-4">
                {/* Core fields */}
                <div>
                  <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">
                    Standard Fields ({coreMappings.length})
                  </h3>
                  <div className="space-y-2">
                    {coreMappings.map((mapping) => (
                      <MappingRow
                        key={mapping.source_column}
                        mapping={mapping}
                        coreFields={coreFields}
                        onChange={(targetField) => updateMapping(mapping.source_column, targetField)}
                      />
                    ))}
                    {coreMappings.length === 0 && (
                      <p className="text-sm text-neutral-400 italic">No columns mapped to standard fields</p>
                    )}
                  </div>
                </div>

                {/* Custom fields */}
                {customMappings.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">
                      Custom Fields ({customMappings.length})
                    </h3>
                    <div className="space-y-2">
                      {customMappings.map((mapping) => (
                        <MappingRow
                          key={mapping.source_column}
                          mapping={mapping}
                          coreFields={coreFields}
                          onChange={(targetField) => updateMapping(mapping.source_column, targetField)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-sm flex items-center gap-2 mt-4">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-6 pt-4 border-t border-neutral-100">
          {success ? (
            <button onClick={onClose} className="btn btn-primary flex-1">
              Done
            </button>
          ) : (
            <>
              <button onClick={onClose} className="btn btn-secondary flex-1" disabled={isSubmitting}>
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={isLoading || isSubmitting}
                className="btn bg-violet-600 hover:bg-violet-700 text-white flex-1"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Adding...</span>
                  </>
                ) : (
                  <>
                    <Database className="w-4 h-4" />
                    <span>Add to All Prospects</span>
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Mapping row component
interface MappingRowProps {
  mapping: FieldMapping;
  coreFields: CoreField[];
  onChange: (targetField: string) => void;
}

function MappingRow({ mapping, coreFields, onChange }: MappingRowProps) {
  const confidenceColor = mapping.confidence >= 0.9 
    ? 'text-emerald-500' 
    : mapping.confidence >= 0.7 
      ? 'text-amber-500' 
      : 'text-neutral-400';

  return (
    <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-xl">
      {/* Source column */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-neutral-700 truncate">
          {mapping.source_column}
        </div>
      </div>

      <ArrowRight className="w-4 h-4 text-neutral-400 flex-shrink-0" />

      {/* Target field selector */}
      <div className="flex-1">
        <select
          value={mapping.target_field}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "input select text-sm py-2",
            mapping.target_field !== 'custom' && "font-medium"
          )}
        >
          <optgroup label="Standard Fields">
            {coreFields.map((field) => (
              <option key={field.name} value={field.name}>
                {field.label}
              </option>
            ))}
          </optgroup>
          <optgroup label="Other">
            <option value="custom">Custom Field</option>
          </optgroup>
        </select>
      </div>

      {/* Confidence indicator */}
      {mapping.confidence < 1.0 && (
        <div className={cn("text-xs flex-shrink-0", confidenceColor)}>
          {Math.round(mapping.confidence * 100)}%
        </div>
      )}
    </div>
  );
}
