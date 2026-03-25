import { useEffect, useRef, useState } from 'react'

export function useSSE(url: string) {
  const [data, setData] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => setConnected(true)
    es.onmessage = (e) => setData(prev => [...prev, e.data])
    es.onerror = () => setConnected(false)

    return () => { es.close() }
  }, [url])

  return { data, connected }
}
