import { useEffect, useState } from 'react';
import { Plus, FileText, Edit2, Trash2, X, Save, Sparkles, Tag } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { templatesApi } from '../api';
import { cn } from '../lib/utils';
import type { PromptTemplate } from '../types';

export function TemplatesPage() {
  const { templates, setTemplates, addTemplate } = useAppStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Partial<PromptTemplate> & { tagsInput?: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const data = await templatesApi.list();
      setTemplates(data);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  };

  // Get all unique tags
  const allTags = Array.from(new Set(templates.flatMap(t => t.tags || [])));

  // Filter templates by selected tag
  const filteredTemplates = selectedTag 
    ? templates.filter(t => t.tags?.includes(selectedTag))
    : templates;

  const handleCreate = () => {
    setEditingTemplate({
      name: '',
      tags: [],
      tagsInput: '',
      prompt_template: '',
      output_column: '',
    });
    setIsEditing(true);
  };

  const handleEdit = (template: PromptTemplate) => {
    if (template.is_system) return;
    setEditingTemplate({ 
      ...template, 
      tagsInput: (template.tags || []).join(', ')
    });
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!editingTemplate) return;

    setIsLoading(true);
    try {
      const tags = editingTemplate.tagsInput
        ?.split(',')
        .map(t => t.trim())
        .filter(Boolean) || [];

      if (editingTemplate.id) {
        const updated = await templatesApi.update(editingTemplate.id, {
          name: editingTemplate.name,
          tags: tags,
          prompt_template: editingTemplate.prompt_template,
          output_column: editingTemplate.output_column,
        });
        setTemplates(templates.map((t) => (t.id === updated.id ? updated : t)));
      } else {
        const created = await templatesApi.create({
          name: editingTemplate.name!,
          tags: tags,
          prompt_template: editingTemplate.prompt_template!,
          output_column: editingTemplate.output_column!,
        });
        addTemplate(created);
      }
      setIsEditing(false);
      setEditingTemplate(null);
    } catch (err) {
      console.error('Failed to save template:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (template: PromptTemplate) => {
    if (template.is_system) return;
    if (!confirm(`Delete "${template.name}"?`)) return;

    try {
      await templatesApi.delete(template.id);
      setTemplates(templates.filter((t) => t.id !== template.id));
    } catch (err) {
      console.error('Failed to delete template:', err);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Prompt Templates</h1>
          <p className="text-sm text-neutral-500 mt-1">Reusable prompts for data enrichment</p>
        </div>
        <button onClick={handleCreate} className="btn btn-primary">
          <Plus className="w-4 h-4" />
          <span>New Template</span>
        </button>
      </div>

      {/* Tags filter */}
      {allTags.length > 0 && (
        <div className="flex items-center gap-2 mb-6 flex-wrap">
          <Tag className="w-4 h-4 text-neutral-400" />
          <button
            onClick={() => setSelectedTag(null)}
            className={cn(
              'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
              !selectedTag
                ? 'bg-orange-500 text-white'
                : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
            )}
          >
            All
          </button>
          {allTags.map(tag => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag === selectedTag ? null : tag)}
              className={cn(
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                selectedTag === tag
                  ? 'bg-orange-500 text-white'
                  : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              )}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* Templates grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredTemplates.map((template) => (
          <div
            key={template.id}
            className={cn(
              'card card-hover p-5 group',
              template.is_system && 'ring-2 ring-orange-200'
            )}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={cn(
                  'w-10 h-10 rounded-xl flex items-center justify-center',
                  template.is_system 
                    ? 'bg-orange-100' 
                    : 'bg-neutral-100'
                )}>
                  {template.is_system ? (
                    <Sparkles className="w-5 h-5 text-orange-500" />
                  ) : (
                    <FileText className="w-5 h-5 text-neutral-500" />
                  )}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-neutral-900">{template.name}</h3>
                  {template.tags && template.tags.length > 0 && (
                    <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                      {template.tags.slice(0, 3).map(tag => (
                        <span 
                          key={tag}
                          className="text-xs px-1.5 py-0.5 bg-orange-50 text-orange-600 rounded-md"
                        >
                          {tag}
                        </span>
                      ))}
                      {template.tags.length > 3 && (
                        <span className="text-xs text-neutral-400">
                          +{template.tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
              {!template.is_system && (
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleEdit(template)}
                    className="p-2 hover:bg-neutral-100 rounded-lg transition-colors"
                  >
                    <Edit2 className="w-3.5 h-3.5 text-neutral-400" />
                  </button>
                  <button
                    onClick={() => handleDelete(template)}
                    className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-500" />
                  </button>
                </div>
              )}
            </div>

            <div className="p-3 rounded-xl bg-neutral-50 text-xs font-mono text-neutral-600 line-clamp-2 mt-3">
              {template.prompt_template}
            </div>

            <div className="mt-4 flex items-center justify-between text-xs">
              <span className="text-neutral-500">
                → <span className="font-medium text-neutral-700">{template.output_column}</span>
              </span>
              {template.is_system && (
                <span className="px-2 py-0.5 bg-orange-100 text-orange-600 rounded-full text-xs font-medium">
                  System
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {filteredTemplates.length === 0 && (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-neutral-200 mx-auto mb-3" />
          <p className="text-neutral-500">No templates found</p>
          {selectedTag && (
            <button
              onClick={() => setSelectedTag(null)}
              className="text-orange-500 hover:text-orange-600 text-sm mt-2"
            >
              Clear filter
            </button>
          )}
        </div>
      )}

      {/* Edit modal */}
      {isEditing && editingTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setIsEditing(false)}
          />
          <div className="relative modal-content w-full max-w-xl p-6 max-h-[85vh] overflow-auto animate-slide-up">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-neutral-900">
                {editingTemplate.id ? 'Edit Template' : 'New Template'}
              </h2>
              <button
                onClick={() => setIsEditing(false)}
                className="p-2 rounded-lg hover:bg-neutral-100 transition-colors"
              >
                <X className="w-4 h-4 text-neutral-500" />
              </button>
            </div>

            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Name</label>
                  <input
                    type="text"
                    value={editingTemplate.name || ''}
                    onChange={(e) =>
                      setEditingTemplate({ ...editingTemplate, name: e.target.value })
                    }
                    className="input"
                    placeholder="Template name"
                  />
                </div>
                <div>
                  <label className="label">Output Column</label>
                  <input
                    type="text"
                    value={editingTemplate.output_column || ''}
                    onChange={(e) =>
                      setEditingTemplate({ ...editingTemplate, output_column: e.target.value })
                    }
                    className="input font-mono"
                    placeholder="column_name"
                  />
                </div>
              </div>

              <div>
                <label className="label">Tags</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {(editingTemplate.tagsInput || '').split(',').filter(t => t.trim()).map((tag, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-orange-50 text-orange-700 rounded-lg text-sm font-medium"
                    >
                      {tag.trim()}
                      <button
                        type="button"
                        onClick={() => {
                          const tags = (editingTemplate.tagsInput || '').split(',').filter(t => t.trim());
                          tags.splice(idx, 1);
                          setEditingTemplate({ ...editingTemplate, tagsInput: tags.join(', ') });
                        }}
                        className="hover:text-orange-900"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
                <input
                  type="text"
                  value={editingTemplate.tagsInput || ''}
                  onChange={(e) =>
                    setEditingTemplate({ ...editingTemplate, tagsInput: e.target.value })
                  }
                  className="input"
                  placeholder="Type tags separated by commas"
                />
              </div>

              <div>
                <label className="label">Prompt Template</label>
                <textarea
                  value={editingTemplate.prompt_template || ''}
                  onChange={(e) =>
                    setEditingTemplate({ ...editingTemplate, prompt_template: e.target.value })
                  }
                  className="input textarea min-h-[200px] font-mono text-sm resize-y"
                  placeholder="Use {{column}} for placeholders..."
                />
                <p className="mt-2 text-xs text-neutral-500">
                  Use {"{{column}}"} to reference data columns
                </p>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setIsEditing(false)}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={isLoading || !editingTemplate.name || !editingTemplate.prompt_template || !editingTemplate.output_column}
                  className="btn btn-primary flex-1"
                >
                  <Save className="w-4 h-4" />
                  <span>Save Template</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
