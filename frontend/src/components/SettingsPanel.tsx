import { useState } from 'react'

export default function SettingsPanel() {
  const [open, setOpen] = useState(false)
  const [sections, setSections] = useState({
    volume: true,
    velocity: true,
    composition: true,
    collaboration: true,
  })
  const [outliers, setOutliers] = useState(false)

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
            {Object.entries(sections).map(([key, val]) => (
              <label key={key} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={val}
                  onChange={e => setSections({ ...sections, [key]: e.target.checked })}
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
              checked={outliers}
              onChange={e => setOutliers(e.target.checked)}
              className="rounded"
            />
            <span>Outlier color encoding</span>
          </label>
        </div>
      )}
    </div>
  )
}
