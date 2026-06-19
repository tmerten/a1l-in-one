import { useSearchParams } from 'react-router-dom'

type ViewMode = 'grouped' | 'timeline'

interface ViewToggleProps {
  defaultValue?: ViewMode
}

export default function ViewToggle({ defaultValue = 'grouped' }: ViewToggleProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentView = (searchParams.get('view') as ViewMode) || defaultValue

  const setView = (view: ViewMode) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('view', view)
    setSearchParams(newParams, { replace: true })
  }

  return (
    <div className="inline-flex rounded-md border border-gray-300 overflow-hidden">
      <button
        className={`px-3 py-1.5 text-sm font-medium ${
          currentView === 'grouped'
            ? 'bg-gray-900 text-white'
            : 'bg-white text-gray-700 hover:bg-gray-50'
        }`}
        onClick={() => setView('grouped')}
      >
        Grouped
      </button>
      <button
        className={`px-3 py-1.5 text-sm font-medium border-l border-gray-300 ${
          currentView === 'timeline'
            ? 'bg-gray-900 text-white'
            : 'bg-white text-gray-700 hover:bg-gray-50'
        }`}
        onClick={() => setView('timeline')}
      >
        Timeline
      </button>
    </div>
  )
}
