import { useState, useEffect, useRef, useCallback } from 'react';
import { Building2, Target, Mic2, Trophy, DollarSign, Calendar, Swords } from 'lucide-react';
import * as kb from '../api/knowledgeBase';
import { cn } from '../lib/utils';

interface TagAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  company: <Building2 className="w-3.5 h-3.5" />,
  segment: <Target className="w-3.5 h-3.5" />,
  voice: <Mic2 className="w-3.5 h-3.5" />,
  case: <Trophy className="w-3.5 h-3.5" />,
  pricing: <DollarSign className="w-3.5 h-3.5" />,
  booking: <Calendar className="w-3.5 h-3.5" />,
  competitor: <Swords className="w-3.5 h-3.5" />,
};

const TYPE_COLORS: Record<string, string> = {
  company: 'bg-blue-100 text-blue-700',
  segment: 'bg-purple-100 text-purple-700',
  voice: 'bg-green-100 text-green-700',
  case: 'bg-yellow-100 text-yellow-700',
  pricing: 'bg-pink-100 text-pink-700',
  booking: 'bg-orange-100 text-orange-700',
  competitor: 'bg-red-100 text-red-700',
};

export function TagAutocomplete({ value, onChange, placeholder, rows = 4, className }: TagAutocompleteProps) {
  const [tags, setTags] = useState<kb.KBTag[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [filteredTags, setFilteredTags] = useState<kb.KBTag[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load tags on mount
  useEffect(() => {
    kb.getAvailableTags().then(data => setTags(data.tags)).catch(console.error);
  }, []);

  // Find current tag being typed
  const getCurrentTagQuery = useCallback(() => {
    const beforeCursor = value.slice(0, cursorPosition);
    const match = beforeCursor.match(/@(\S*)$/);
    return match ? match[1] : null;
  }, [value, cursorPosition]);

  // Filter tags based on current query
  useEffect(() => {
    const query = getCurrentTagQuery();
    if (query !== null) {
      const filtered = tags.filter(tag => 
        tag.tag.toLowerCase().includes(`@${query}`.toLowerCase()) ||
        tag.label.toLowerCase().includes(query.toLowerCase())
      );
      setFilteredTags(filtered);
      setShowDropdown(filtered.length > 0);
      setSelectedIndex(0);
    } else {
      setShowDropdown(false);
    }
  }, [value, cursorPosition, tags, getCurrentTagQuery]);

  const insertTag = (tag: kb.KBTag) => {
    const beforeCursor = value.slice(0, cursorPosition);
    const afterCursor = value.slice(cursorPosition);
    const tagStart = beforeCursor.lastIndexOf('@');
    
    const newValue = beforeCursor.slice(0, tagStart) + tag.tag + ' ' + afterCursor;
    onChange(newValue);
    setShowDropdown(false);
    
    // Focus back on textarea
    setTimeout(() => {
      if (textareaRef.current) {
        const newPosition = tagStart + tag.tag.length + 1;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newPosition, newPosition);
      }
    }, 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, filteredTags.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && filteredTags[selectedIndex]) {
      e.preventDefault();
      insertTag(filteredTags[selectedIndex]);
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    } else if (e.key === 'Tab' && filteredTags[selectedIndex]) {
      e.preventDefault();
      insertTag(filteredTags[selectedIndex]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
    setCursorPosition(e.target.selectionStart);
  };

  const handleSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    setCursorPosition((e.target as HTMLTextAreaElement).selectionStart);
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onSelect={handleSelect}
        onKeyDown={handleKeyDown}
        onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
        placeholder={placeholder || "Write your prompt... Use @ to reference knowledge base"}
        rows={rows}
        className={cn("input w-full font-mono text-sm", className)}
      />
      
      {/* Tag hint */}
      <div className="absolute right-2 top-2 text-xs text-neutral-400">
        Type <span className="font-mono bg-neutral-100 px-1 rounded">@</span> for KB tags
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div 
          ref={dropdownRef}
          className="absolute z-50 mt-1 w-80 max-h-64 overflow-auto bg-white border border-neutral-200 rounded-lg shadow-lg"
        >
          {filteredTags.map((tag, index) => (
            <div
              key={tag.tag}
              onClick={() => insertTag(tag)}
              className={cn(
                "flex items-center gap-3 px-3 py-2 cursor-pointer",
                index === selectedIndex ? "bg-neutral-100" : "hover:bg-neutral-50"
              )}
            >
              <div className={cn("w-7 h-7 rounded flex items-center justify-center", TYPE_COLORS[tag.type])}>
                {TYPE_ICONS[tag.type]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-neutral-900 truncate">{tag.label}</div>
                <div className="text-xs text-neutral-500 truncate">{tag.tag}</div>
              </div>
              <div className="text-xs text-neutral-400 truncate max-w-[100px]">
                {tag.description}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Simpler inline tag picker for single selection
export function TagPicker({ 
  type, 
  value, 
  onChange,
  placeholder = "Select..."
}: { 
  type: kb.KBTag['type']; 
  value: string; 
  onChange: (tag: string) => void;
  placeholder?: string;
}) {
  const [tags, setTags] = useState<kb.KBTag[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    kb.getAvailableTags().then(data => {
      setTags(data.tags.filter(t => t.type === type));
    }).catch(console.error);
  }, [type]);

  const selectedTag = tags.find(t => t.tag === value);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "input w-full text-left flex items-center justify-between",
          !selectedTag && "text-neutral-400"
        )}
      >
        <span>{selectedTag?.label || placeholder}</span>
        <span className="text-neutral-400">▼</span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-48 overflow-auto bg-white border border-neutral-200 rounded-lg shadow-lg">
          <div
            onClick={() => { onChange(''); setOpen(false); }}
            className="px-3 py-2 text-sm text-neutral-500 hover:bg-neutral-50 cursor-pointer"
          >
            None
          </div>
          {tags.map(tag => (
            <div
              key={tag.tag}
              onClick={() => { onChange(tag.tag); setOpen(false); }}
              className={cn(
                "px-3 py-2 cursor-pointer hover:bg-neutral-50",
                tag.tag === value && "bg-neutral-100"
              )}
            >
              <div className="text-sm font-medium text-neutral-900">{tag.label}</div>
              <div className="text-xs text-neutral-500">{tag.description}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
