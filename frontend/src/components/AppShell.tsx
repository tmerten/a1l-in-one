import { Link, Outlet, useLocation } from 'react-router-dom'
import { useSyncStatus } from '../hooks/useMetrics'
import TimeframeSelector from './TimeframeSelector'
import ProjectFilter from './ProjectFilter'
import SyncStatusBadge from './SyncStatusBadge'

export default function AppShell() {
  const location = useLocation()
  const { data: syncStatus } = useSyncStatus()

  const tab = location.pathname.includes('/people') ? 'people' : 'projects'

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <h1 className="text-xl font-semibold text-gray-900">Project Health</h1>
              <nav className="flex gap-1">
                <Link
                  to="/projects"
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    tab === 'projects'
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  Projects
                </Link>
                <Link
                  to="/people"
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    tab === 'people'
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  People
                </Link>
              </nav>
            </div>
            <SyncStatusBadge status={syncStatus} />
          </div>
          <div className="mt-3 flex items-center gap-4 flex-wrap">
            <TimeframeSelector />
            <ProjectFilter />
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
