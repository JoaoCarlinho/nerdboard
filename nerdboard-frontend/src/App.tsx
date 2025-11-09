import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Link, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import './App.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30000, // Auto-refresh every 30 seconds (Story 4.9)
      staleTime: 25000,
    },
  },
})

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || 'demo_token_12345'

// API client
const api = {
  get: async (url: string) => {
    const res = await fetch(`${API_URL}${url}`, {
      headers: { 'Authorization': `Bearer ${API_TOKEN}` }
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }
}

// Story 4.2: Dashboard Layout & Navigation
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <header className="header">
        <h1>NerdBoard</h1>
        <p>AI-Powered Operations Intelligence</p>
      </header>
      <nav className="nav">
        <Link to="/">Dashboard</Link>
        <Link to="/predictions">Predictions</Link>
      </nav>
      <main className="main">{children}</main>
      <footer className="footer">
        Last updated: {new Date().toLocaleTimeString()}
      </footer>
    </div>
  )
}

// Story 4.6: Metrics Dashboard Cards
function MetricsCards() {
  const { data } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.get('/api/v1/dashboard/metrics')
  })

  if (!data) return <div>Loading metrics...</div>

  const metrics = [
    { label: 'Avg Health Score', value: `${data.avg_health_score}%`, trend: '+2%' },
    { label: 'Session Success', value: `${data.first_session_success_rate}%`, trend: '+5%' },
    { label: 'Session Velocity', value: data.session_velocity.toFixed(1), trend: '-1%' },
    { label: 'Churn Risks', value: data.churn_risk_count, trend: '-3' },
    { label: 'Supply/Demand', value: data.supply_demand_ratio.toFixed(2), trend: '+0.1' },
  ]

  return (
    <div className="metrics-grid">
      {metrics.map((m, i) => (
        <div key={i} className="metric-card">
          <div className="metric-label">{m.label}</div>
          <div className="metric-value">{m.value}</div>
          <div className="metric-trend">{m.trend}</div>
        </div>
      ))}
    </div>
  )
}

// Story 4.3: Subject Capacity Overview Grid
function SubjectGrid() {
  const { data } = useQuery({
    queryKey: ['overview'],
    queryFn: () => api.get('/api/v1/dashboard/overview')
  })

  if (!data) return <div>Loading subjects...</div>

  return (
    <div className="subject-grid">
      {data.subjects.map((subject: any) => {
        const status = subject.predicted_status
        const statusColor = status === 'critical' ? 'red' : status === 'warning' ? 'orange' : 'green'

        return (
          <Link key={subject.subject} to={`/subject/${subject.subject}`} className="subject-card">
            <div className="subject-header">
              <h3>{subject.subject}</h3>
              <span className={`status-badge status-${statusColor}`}>{status}</span>
            </div>
            <div className="subject-stats">
              <div className="stat">
                <span className="stat-label">Utilization</span>
                <span className="stat-value">{subject.current_utilization}%</span>
              </div>
              <div className="stat">
                <span className="stat-label">Tutors</span>
                <span className="stat-value">{subject.tutor_count}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Alerts</span>
                <span className="stat-value alert-count">{subject.active_alerts_count}</span>
              </div>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

// Story 4.4: Predictions Alert Feed + Story 4.8: Filtering & Sorting
function PredictionsFeed() {
  const [filters, setFilters] = useState({ subject: '', urgency: '', sort: 'priority_desc' })
  const [selectedPrediction, setSelectedPrediction] = useState<string | null>(null)

  const { data } = useQuery({
    queryKey: ['predictions', filters],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filters.subject) params.append('subject', filters.subject)
      if (filters.urgency) params.append('urgency', filters.urgency)
      params.append('sort', filters.sort)
      return api.get(`/api/v1/predictions?${params}`)
    }
  })

  return (
    <div className="predictions-container">
      {/* Story 4.8: Filtering Controls */}
      <div className="filters">
        <select value={filters.subject} onChange={(e) => setFilters({...filters, subject: e.target.value})}>
          <option value="">All Subjects</option>
          <option value="Physics">Physics</option>
          <option value="Math">Math</option>
          <option value="SAT Prep">SAT Prep</option>
        </select>
        <select value={filters.urgency} onChange={(e) => setFilters({...filters, urgency: e.target.value})}>
          <option value="">All Urgency</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
        </select>
        <select value={filters.sort} onChange={(e) => setFilters({...filters, sort: e.target.value})}>
          <option value="priority_desc">Priority (High to Low)</option>
          <option value="date_desc">Date (Soonest)</option>
          <option value="confidence_desc">Confidence (Highest)</option>
        </select>
      </div>

      {/* Story 4.4: Alert Feed */}
      <div className="predictions-feed">
        {!data ? <div>Loading predictions...</div> : (
          data.predictions.map((pred: any) => (
            <div
              key={pred.prediction_id}
              className={`prediction-card ${pred.is_critical ? 'critical' : ''}`}
              onClick={() => setSelectedPrediction(pred.prediction_id)}
            >
              <div className="prediction-header">
                <h4>{pred.subject}</h4>
                <span className={`severity-${pred.severity}`}>{pred.severity}</span>
              </div>
              <div className="prediction-body">
                <p><strong>{(pred.shortage_probability * 100).toFixed(0)}%</strong> probability</p>
                <p>In <strong>{pred.days_until_shortage}</strong> days</p>
                <p>Confidence: <strong>{pred.confidence_score}%</strong></p>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Story 4.5: Prediction Detail Drawer */}
      {selectedPrediction && (
        <PredictionDrawer
          predictionId={selectedPrediction}
          onClose={() => setSelectedPrediction(null)}
        />
      )}
    </div>
  )
}

// Story 4.5: Prediction Detail Drawer/Panel
function PredictionDrawer({ predictionId, onClose }: { predictionId: string, onClose: () => void }) {
  const { data } = useQuery({
    queryKey: ['prediction', predictionId],
    queryFn: () => api.get(`/api/v1/predictions/${predictionId}`)
  })

  if (!data) return null

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h2>{data.subject} Capacity Shortage Prediction</h2>
          <button onClick={onClose}>✕</button>
        </div>

        <div className="drawer-content">
          <div className="prediction-summary">
            <div className="summary-item">
              <span>Probability</span>
              <strong>{(data.shortage_probability * 100).toFixed(0)}%</strong>
            </div>
            <div className="summary-item">
              <span>Days Until</span>
              <strong>{data.days_until_shortage}</strong>
            </div>
            <div className="summary-item">
              <span>Severity</span>
              <strong className={`severity-${data.severity}`}>{data.severity}</strong>
            </div>
            <div className="summary-item">
              <span>Confidence</span>
              <strong>{data.confidence_score}%</strong>
            </div>
          </div>

          <div className="explanation-section">
            <h3>Why This Prediction?</h3>
            <div className="contributing-factors">
              {data.top_features?.slice(0, 3).map((feat: any, i: number) => (
                <div key={i} className="factor">
                  <div className="factor-label">{i + 1}. {feat.readable_description}</div>
                  <div className="factor-bar">
                    <div
                      className="factor-fill"
                      style={{ width: `${Math.abs(feat.importance) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="explanation-text">
            <h3>Detailed Explanation</h3>
            <p>{data.explanation_text}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Story 4.7: Subject Detail View
function SubjectDetail() {
  const { subject } = useParams<{ subject: string }>()

  const { data } = useQuery({
    queryKey: ['subject', subject],
    queryFn: () => api.get(`/api/v1/dashboard/subjects/${subject}`)
  })

  if (!data) return <div>Loading subject detail...</div>

  return (
    <div className="subject-detail">
      <div className="detail-header">
        <Link to="/" className="back-button">← Back to Dashboard</Link>
        <h2>{subject}</h2>
      </div>

      <div className="detail-metrics">
        <div className="detail-metric">
          <span>Current Utilization</span>
          <strong>{data.current_utilization}%</strong>
        </div>
        <div className="detail-metric">
          <span>Tutors</span>
          <strong>{data.tutor_count}</strong>
        </div>
        <div className="detail-metric">
          <span>Capacity (hrs/week)</span>
          <strong>{data.capacity_hours}</strong>
        </div>
      </div>

      <div className="detail-sections">
        <div className="detail-section">
          <h3>Active Predictions</h3>
          <div className="predictions-list">
            {data.predictions?.map((pred: any) => (
              <div key={pred.prediction_id} className="prediction-item">
                <span>{pred.days_until_shortage} days</span>
                <span>{(pred.shortage_probability * 100).toFixed(0)}% prob</span>
                <span className={`severity-${pred.severity}`}>{pred.severity}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="detail-section">
          <h3>Top Tutors</h3>
          <div className="tutors-list">
            {data.tutors?.slice(0, 5).map((tutor: any, i: number) => (
              <div key={i} className="tutor-item">
                <span>{tutor.tutor_id}</span>
                <span>{tutor.utilization.toFixed(0)}% utilized</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// Story 4.2: Main Dashboard
function Dashboard() {
  return (
    <div className="dashboard">
      <h2 className="dashboard-title">Operations Dashboard</h2>
      <MetricsCards />
      <h3 className="section-title">Subject Capacity Overview</h3>
      <SubjectGrid />
    </div>
  )
}

// Main App (Story 4.1, 4.2, 4.9)
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/predictions" element={<PredictionsFeed />} />
            <Route path="/subject/:subject" element={<SubjectDetail />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
