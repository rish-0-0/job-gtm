import { ReactNode } from 'react'
import Sidebar from './Sidebar'

interface LayoutProps {
  children: ReactNode
}

function Layout({ children }: LayoutProps) {
  return (
    <div className="app">
      <Sidebar />
      <main className="main-content">{children}</main>
    </div>
  )
}

export default Layout
