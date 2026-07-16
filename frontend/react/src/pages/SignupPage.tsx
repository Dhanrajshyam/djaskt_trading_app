import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { Activity } from 'lucide-react'
import { signup, login } from '../features/auth/authApi'
import { useAuthStore } from '../features/auth/authStore'
import { ApiError } from '../lib/apiClient'
import { Button } from '../components/ui/Button'

export default function SignupPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((state) => state.setTokens)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await signup({ email, password, first_name: firstName, last_name: lastName })
      // Signup doesn't return tokens (see accounts/api.py) — log in
      // immediately afterward so the user doesn't have to enter their
      // password twice.
      const result = await login({ email, password })
      setTokens({ email: result.email, access: result.access, refresh: result.refresh })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="p-3 bg-indigo-600 rounded-xl mb-3">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">Create your account</h1>
        </div>

        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          {error && (
            <div className="bg-rose-400/10 border border-rose-400/30 text-rose-300 text-sm rounded p-3">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1" htmlFor="firstName">
                First name
              </label>
              <input
                id="firstName"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1" htmlFor="lastName">
                Last name
              </label>
              <input
                id="lastName"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <Button type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? 'Creating account…' : 'Sign up'}
          </Button>

          <p className="text-sm text-slate-400 text-center">
            Already have an account?{' '}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300">
              Log in
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
