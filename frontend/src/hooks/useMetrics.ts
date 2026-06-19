import { useQuery } from '@tanstack/react-query'
import {
  getMetrics, getMetricsTs, getProjects, getSyncStatus, getSprints,
  getPersons, getPersonContributions, getWorkItems, getCommits,
} from '../api/client'
import type { WorkItemsParams, CommitsParams } from '../api/client'

export function useSyncStatus() {
  return useQuery({
    queryKey: ['syncStatus'],
    queryFn: getSyncStatus,
    refetchInterval: (query) => query.state.data?.any_running ? 2000 : false,
  })
}

export function useSprints(project?: string) {
  return useQuery({ queryKey: ['sprints', project], queryFn: () => getSprints(project) })
}

export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
}

export function useContributionVolume(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'contribution-volume', query], queryFn: () => getMetrics('contribution-volume', query) })
}

export function useVelocity(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'velocity', query], queryFn: () => getMetrics('velocity', query) })
}

export function useComposition(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'composition', query], queryFn: () => getMetrics('composition', query) })
}

export function useCollaboration(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'collaboration', query], queryFn: () => getMetrics('collaboration', query) })
}

export function useSprintBurndown(sprintId: string) {
  return useQuery({ queryKey: ['metrics', 'sprint-burndown', sprintId], queryFn: () => getMetrics('sprint-burndown', { sprint_id: sprintId }) })
}

export function useContributionVolumeTs(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'contribution-volume-ts', query], queryFn: () => getMetricsTs('contribution-volume', query) })
}

export function useVelocityTs(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'velocity-ts', query], queryFn: () => getMetricsTs('velocity', query) })
}

export function useCollaborationTs(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['metrics', 'collaboration-ts', query], queryFn: () => getMetricsTs('collaboration', query) })
}

export function usePersons(query: Record<string, string | string[] | undefined>) {
  return useQuery({ queryKey: ['persons', query], queryFn: () => getPersons(query) })
}

export function usePersonContributions(personId: string, query: Record<string, string | string[] | undefined>) {
  return useQuery({
    queryKey: ['personContributions', personId, query],
    queryFn: () => getPersonContributions(personId, query),
    enabled: !!personId,
  })
}

export function useWorkItems(personId: string, query: WorkItemsParams) {
  return useQuery({
    queryKey: ['workItems', personId, query],
    queryFn: () => getWorkItems(personId, query),
    enabled: !!personId,
  })
}

export function useCommits(personId: string, query: CommitsParams) {
  return useQuery({
    queryKey: ['commits', personId, query],
    queryFn: () => getCommits(personId, query),
    enabled: !!personId,
  })
}