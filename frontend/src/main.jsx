import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from './App'
import { AccountProvider } from './context/AccountContext'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Refetch stale data after 30 seconds (matches backend metric interval)
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AccountProvider>
          <App />
        </AccountProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
