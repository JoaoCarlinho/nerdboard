# NerdBoard Frontend

AI-Powered Operations Intelligence Platform - React Dashboard

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development
- **React Router** for navigation
- **TanStack Query** for data fetching and caching
- **Axios** for API calls
- **Recharts** for data visualization (ready to use)
- **Lucide React** for icons

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Build

```bash
npm run build
```

### Environment Variables

Create a `.env` file:

```
VITE_API_URL=http://localhost:8000
VITE_API_TOKEN=demo_token_12345
```

## Features

### ✅ Story 4.1: React Project Setup
- Vite + React + TypeScript
- TanStack Query for data management
- React Router for routing
- Modern development setup

### ✅ Story 4.2: Dashboard Layout & Navigation
- Header with branding
- Navigation bar with routing
- Footer with last updated timestamp
- Responsive layout

### ✅ Story 4.3: Subject Capacity Overview Grid
- Grid of all subjects
- Color-coded status indicators (green/yellow/red)
- Utilization percentages
- Active alert counts
- Clickable cards navigate to subject detail

### ✅ Story 4.4: Predictions Alert Feed
- Sorted by priority (default)
- Shows shortage probability, days until, confidence
- Color-coded by severity
- Critical predictions highlighted
- Click to open detail drawer

### ✅ Story 4.5: Prediction Detail Drawer
- Slides in from right
- Shows full prediction details
- SHAP feature contributions with visual bars
- Natural language explanation
- Dismiss with click outside or close button

### ✅ Story 4.6: Metrics Dashboard Cards
- 5 key operational metrics
- Large numbers with trend indicators
- Grid layout
- Hover effects

### ✅ Story 4.7: Subject Detail View
- Dedicated route `/subject/:subject`
- Shows utilization, tutor count, capacity
- Lists active predictions
- Shows top tutors
- Back button to dashboard

### ✅ Story 4.8: Filtering & Sorting Controls
- Filter by subject
- Filter by urgency level
- Sort by priority, date, or confidence
- Filters update query parameters
- Real-time filtering

### ✅ Story 4.9: Real-Time Updates & Auto-Refresh
- Automatic refresh every 30 seconds
- TanStack Query handles caching
- Stale time: 25 seconds
- Background refetching
- Last updated timestamp in footer

## API Integration

All API calls use bearer token authentication. The token is configured in `.env`.

### Endpoints Used

- `GET /api/v1/dashboard/overview` - Subject overview
- `GET /api/v1/dashboard/metrics` - Operational metrics
- `GET /api/v1/dashboard/subjects/:subject` - Subject detail
- `GET /api/v1/predictions` - List predictions
- `GET /api/v1/predictions/:id` - Prediction detail

## Project Structure

```
src/
├── App.tsx          # Main application with all components
├── App.css          # Complete styling
├── main.tsx         # React entry point
└── index.css        # Global styles
```

## Design Decisions

- **Single-file components**: For rapid development and easy maintenance in MVP
- **Inline API client**: Simple fetch-based API for minimal dependencies
- **Auto-refresh**: TanStack Query handles this elegantly
- **Responsive**: Mobile-first CSS Grid and Flexbox
- **Color scheme**: Blue primary, status colors (green/yellow/red)
- **Professional**: Clean, operations-focused UI without unnecessary decoration

## Performance

- Auto-refresh: 30 seconds
- Stale time: 25 seconds
- Response caching with TanStack Query
- Minimal re-renders with React Query
- Code splitting ready (can add route-based splitting)

## Future Enhancements

- Add Recharts visualizations for utilization trends
- Implement toast notifications for new critical alerts
- Add dark mode support
- Enhance filtering with date ranges
- Add export functionality for predictions
- Implement user preferences/settings
