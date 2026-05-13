import { useQuery } from '@tanstack/react-query'
import { getMetrics, getSyncStatus, getSprints } from '../api/client'

export function useSyncStatus() {
  return useQuery({ queryKey: ['syncStatus'], queryFn: getSyncStatus })
}

export function useSprints(project?: string) {
  return useQuery({ queryKey: ['sprints', project], queryFn: () => getSprints(project) })
}

export function useContributionVolume(query: Record<string, string>) {
  return useQuery({ queryKey: ['metrics', 'contribution-volume', query], queryFn: () => getMetrics('contribution-volume', query) })
}

export function useVelocity(query: Record<string, string>) {
  return useQuery({ queryKey: ['metrics', 'velocity', query], queryFn: () => getMetrics('velocity', query) })
}

export function useComposition(query: Record<string, string>) {
  return useQuery({ queryKey: ['metrics', 'composition', query], queryFn: () => getMetrics('composition', query) })
}

export function useCollaboration(query: Record<string, string>) {
  return useQuery({ queryKey: ['metrics', 'collaboration', query], queryFn: () => getMetrics('collaboration', query) })
}

export function useSprintBurndown(sprintId: string) {
  return useQuery({ queryKey: ['metrics', 'sprint-burndown', sprintId], queryFn: () => getMetrics('sprint-burndown', { sprint_id: sprintId }) })
}
