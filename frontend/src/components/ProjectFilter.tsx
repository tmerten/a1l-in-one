export default function ProjectFilter() {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">Projects:</span>
      <select className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white">
        <option value="">All projects</option>
      </select>
    </div>
  )
}
