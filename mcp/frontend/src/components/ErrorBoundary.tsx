import { Component, type ReactNode } from 'react'

export class SectionErrorBoundary extends Component<{ children: ReactNode }, { error: any }> {
  state = { error: null as any }
  static getDerivedStateFromError(error: any) { return { error } }
  render() {
    if (this.state.error) return <div style={{ padding: 20, color: 'var(--danger)' }}>Error: {String(this.state.error)}</div>
    return this.props.children
  }
}
