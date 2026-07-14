import { Navigate } from 'react-router'
import { useAuthStore } from '../features/auth/authStore'

/** Root path (/) redirects to the dashboard if logged in, otherwise to login. */
export default function IndexRedirect() {
  const accessToken = useAuthStore((state) => state.accessToken)
  return <Navigate to={accessToken ? '/dashboard' : '/login'} replace />
}
