import { createBrowserRouter } from 'react-router-dom'
import AppShell from './components/AppShell'
import ProjectsPage from './pages/ProjectsPage'
import PeoplePage from './pages/PeoplePage'
import PersonDetailPage from './pages/PersonDetailPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: 'projects', element: <ProjectsPage /> },
      { path: 'people', element: <PeoplePage /> },
      { path: 'persons/:personId', element: <PersonDetailPage /> },
    ],
  },
])
