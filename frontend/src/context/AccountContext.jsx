/**
 * AccountContext — global account selector state.
 *
 * The selected account filters scripts, variables, and tables
 * to show only those belonging to the active tenant.
 * "global" (null) shows global resources.
 */

import React, { createContext, useContext, useState } from 'react'

const AccountContext = createContext(null)

export function AccountProvider({ children }) {
  // null = show global resources; string = account_id
  const [selectedAccountId, setSelectedAccountId] = useState(null)

  return (
    <AccountContext.Provider value={{ selectedAccountId, setSelectedAccountId }}>
      {children}
    </AccountContext.Provider>
  )
}

export function useAccount() {
  const ctx = useContext(AccountContext)
  if (!ctx) throw new Error('useAccount must be used within AccountProvider')
  return ctx
}
