type Props = {
  value: 'cards' | 'charts'
  onChange: (v: 'cards' | 'charts') => void
}

export default function ChartSectionToggle({ value, onChange }: Props) {
  return (
    <div className="flex rounded-md border border-gray-200 overflow-hidden text-xs">
      {(['cards', 'charts'] as const).map(opt => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`px-2.5 py-1 capitalize ${
            value === opt
              ? 'bg-gray-900 text-white'
              : 'bg-white text-gray-500 hover:bg-gray-50'
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
