import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'

export interface DashboardSettings {
  sections: {
    volume: boolean
    velocity: boolean
    composition: boolean
    collaboration: boolean
  }
  outliers: boolean
  sparklineMetric: 'prs' | 'commits' | 'issues'
}

const DEFAULT_SETTINGS: DashboardSettings = {
  sections: { volume: true, velocity: true, composition: true, collaboration: true },
  outliers: false,
  sparklineMetric: 'prs',
}

const STORAGE_KEY = 'project-health:settings'

function loadSettings(): DashboardSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return DEFAULT_SETTINGS
}

const SettingsContext = createContext<{
  settings: DashboardSettings
  setSettings: (s: DashboardSettings) => void
}>({ settings: DEFAULT_SETTINGS, setSettings: () => {} })

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettingsState] = useState<DashboardSettings>(loadSettings)

  function setSettings(s: DashboardSettings) {
    setSettingsState(s)
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)) } catch { /* ignore */ }
  }

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)) } catch { /* ignore */ }
  }, [settings])

  return <SettingsContext.Provider value={{ settings, setSettings }}>{children}</SettingsContext.Provider>
}

export function useSettings() {
  return useContext(SettingsContext)
}

export default function SettingsPanel() {
  const { settings, setSettings } = useSettings()
  const [open, setOpen] = useState(false)

  function toggleSection(key: keyof DashboardSettings['sections']) {
    setSettings({ ...settings, sections: { ...settings.sections, [key]: !settings.sections[key] } })
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="text-sm text-gray-500 hover:text-gray-900"
      >
        Settings
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-50">
          <h3 className="font-medium text-gray-900 mb-2">Display</h3>
          <div className="space-y-2">
            {(Object.keys(settings.sections) as Array<keyof DashboardSettings['sections']>).map(key => (
              <label key={key} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={settings.sections[key]}
                  onChange={() => toggleSection(key)}
                  className="rounded"
                />
                <span className="capitalize">{key}</span>
              </label>
            ))}
          </div>
          <hr className="my-3" />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={settings.outliers}
              onChange={e => setSettings({ ...settings, outliers: e.target.checked })}
              className="rounded"
            />
            <span>Outlier color encoding</span>
          </label>
          <hr className="my-3" />
          <div className="text-sm">
            <span className="text-gray-600">Sparkline metric: </span>
            <select
              value={settings.sparklineMetric}
              onChange={e => setSettings({ ...settings, sparklineMetric: e.target.value as DashboardSettings['sparklineMetric'] })}
              className="border border-gray-300 rounded px-1 py-0.5 text-xs ml-1"
            >
              <option value="prs">PRs</option>
              <option value="commits">Commits</option>
              <option value="issues">Issues</option>
            </select>
          </div>
        </div>
      )}
    </div>
  )
}
