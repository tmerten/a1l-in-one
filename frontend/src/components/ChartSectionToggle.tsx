type Props<T extends string = 'cards' | 'charts'> = {
  value: T
  onChange: (v: T) => void
  options?: readonly T[]
}

export default function ChartSectionToggle<T extends string = 'cards' | 'charts'>({
  value,
  onChange,
  options,
}: Props<T>) {
  const opts = (options ?? ['cards', 'charts']) as readonly T[]
  return (
    <div className="flex rounded-md border border-gray-200 overflow-hidden text-xs">
      {opts.map(opt => (
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
