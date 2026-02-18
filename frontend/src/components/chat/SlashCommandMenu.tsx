import React, { useState, useEffect, useRef } from 'react';
import {
  Search, Square, Activity, Send, Target, BarChart3, Globe,
  Settings, BookOpen, PenLine, MessageCircle, Mail, ShieldCheck,
  Layers, ToggleLeft, Users, HelpCircle, Eye,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useTheme } from '../../hooks/useTheme';

interface SlashCommand {
  command: string;
  label: string;
  description: string;
  icon: typeof Search;
  example: string;
}

const SLASH_COMMANDS: SlashCommand[] = [
  { command: '/search', label: 'Search', description: 'Start segment-based search pipeline', icon: Search, example: '/search yandex on best segments' },
  { command: '/stats', label: 'Stats', description: 'Show performance analytics', icon: BarChart3, example: '/stats by segment' },
  { command: '/targets', label: 'Targets', description: 'Show top target companies', icon: Target, example: '/targets' },
  { command: '/contacts', label: 'Contacts', description: 'Show CRM contacts with filters', icon: Users, example: '/contacts replied RU' },
  { command: '/push', label: 'Push', description: 'Push contacts to SmartLead', icon: Send, example: '/push all to smartlead' },
  { command: '/status', label: 'Status', description: 'Show pipeline status', icon: Activity, example: '/status' },
  { command: '/stop', label: 'Stop', description: 'Stop running pipeline', icon: Square, example: '/stop' },
  { command: '/knowledge', label: 'Knowledge', description: 'Show knowledge base', icon: BookOpen, example: '/knowledge icp' },
  { command: '/note', label: 'Add Note', description: 'Add a knowledge base entry', icon: PenLine, example: '/note ICP targets luxury RE in Dubai' },
  { command: '/config', label: 'Config', description: 'Show or edit search config', icon: Settings, example: '/config' },
  { command: '/verify', label: 'Verify', description: 'Run email verification', icon: Mail, example: '/verify all emails' },
  { command: '/segments', label: 'Segments', description: 'Show segment breakdown', icon: Layers, example: '/segments' },
  { command: '/funnel', label: 'Funnel', description: 'Show conversion funnel', icon: Eye, example: '/funnel' },
  { command: '/lookup', label: 'Lookup', description: 'Look up specific domains', icon: Globe, example: '/lookup company.com' },
  { command: '/ask', label: 'Ask', description: 'Ask a question about the project', icon: MessageCircle, example: '/ask what is our ICP?' },
];

// Map slash commands to chat messages
export function resolveSlashCommand(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed.startsWith('/')) return null;

  const parts = trimmed.split(/\s+/);
  const cmd = parts[0].toLowerCase();
  const rest = parts.slice(1).join(' ');

  const mapping: Record<string, string> = {
    '/search': rest ? `run search ${rest}` : 'run yandex search',
    '/stats': rest ? `show stats ${rest}` : 'show stats',
    '/targets': 'show targets',
    '/contacts': rest ? `show contacts ${rest}` : 'show contacts',
    '/push': rest ? `push ${rest}` : 'push to smartlead',
    '/status': 'pipeline status',
    '/stop': 'stop',
    '/knowledge': rest ? `show ${rest} knowledge` : 'show knowledge',
    '/note': rest ? `note: ${rest}` : 'show knowledge',
    '/config': rest ? `edit config: ${rest}` : 'show config',
    '/verify': 'verify all emails',
    '/segments': 'show segments',
    '/funnel': 'show funnel',
    '/lookup': rest ? `lookup ${rest}` : 'show targets',
    '/ask': rest || 'what can you tell me about this project?',
  };

  return mapping[cmd] || null;
}

interface SlashCommandMenuProps {
  isOpen: boolean;
  filter: string;
  onSelect: (command: SlashCommand) => void;
  onClose: () => void;
  selectedIndex: number;
}

export function SlashCommandMenu({ isOpen, filter, onSelect, onClose, selectedIndex }: SlashCommandMenuProps) {
  const { isDark } = useTheme();
  const menuRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const filtered = SLASH_COMMANDS.filter(cmd =>
    cmd.command.includes(filter.toLowerCase()) ||
    cmd.label.toLowerCase().includes(filter.toLowerCase().replace('/', ''))
  );

  // Scroll selected item into view
  useEffect(() => {
    if (selectedIndex >= 0 && itemRefs.current[selectedIndex]) {
      itemRefs.current[selectedIndex]?.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  if (!isOpen || filtered.length === 0) return null;

  return (
    <div
      ref={menuRef}
      className={cn(
        "absolute bottom-full left-0 right-0 mb-1 max-h-64 overflow-y-auto rounded-xl shadow-xl border z-50",
        isDark ? "bg-[#2d2d2d] border-[#3c3c3c]" : "bg-white border-gray-200"
      )}
    >
      <div className={cn(
        "px-3 py-1.5 text-[10px] font-medium uppercase tracking-wide border-b",
        isDark ? "text-[#858585] border-[#3c3c3c]" : "text-gray-400 border-gray-100"
      )}>
        Commands
      </div>
      {filtered.map((cmd, i) => {
        const Icon = cmd.icon;
        return (
          <button
            key={cmd.command}
            ref={el => { itemRefs.current[i] = el; }}
            onClick={() => onSelect(cmd)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 text-left transition-colors",
              i === selectedIndex
                ? isDark ? "bg-[#37373d]" : "bg-indigo-50"
                : isDark ? "hover:bg-[#37373d]" : "hover:bg-gray-50"
            )}
          >
            <div className={cn(
              "w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0",
              isDark ? "bg-[#3c3c3c]" : "bg-gray-100"
            )}>
              <Icon className={cn("w-3.5 h-3.5", isDark ? "text-[#b0b0b0]" : "text-gray-500")} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={cn(
                  "text-xs font-mono font-medium",
                  isDark ? "text-indigo-400" : "text-indigo-600"
                )}>
                  {cmd.command}
                </span>
                <span className={cn("text-xs", isDark ? "text-[#858585]" : "text-gray-500")}>
                  {cmd.description}
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
