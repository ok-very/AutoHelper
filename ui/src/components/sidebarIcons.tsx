import {
  BookOpen,
  HeartPulse,
  GitCompare,
  Image,
  Search,
  Users,
  BarChart3,
  Mail,
  Home,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import type { FC } from 'react';

export const SIDEBAR_ICONS: Record<string, FC<{ size?: number }>> = {
  BookOpen,
  HeartPulse,
  GitCompare,
  Image,
  Search,
  Users,
  BarChart3,
  Mail,
};

export { Home, Settings, PanelLeftClose, PanelLeftOpen };
